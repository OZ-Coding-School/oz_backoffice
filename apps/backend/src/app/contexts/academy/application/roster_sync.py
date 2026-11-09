"""Airtable 수강생 명단 동기화 (plan P5, decisions A9·A10·A18·A19).

흐름: 실행 이력 생성(RUNNING) → [워커] Airtable 조회(트랜잭션 밖) → 한 트랜잭션에서
신규 생성·변경 반영·원천 삭제 표시·실행 결과 저장.

- 범위: 전체(별칭이 설정된 과정 전부) / 과정 / 기수. Airtable 수식으로 범위만 읽는다.
- upsert 키는 airtable_record_id. 새 레코드는 미가입 수강생(user_id 없음, 등록일 = 기수 시작일).
- 기존 레코드는 원천 필드(이름·휴대폰·이메일·HRD상태)와 수강 상태(A19)를 맞춘다.
- 원천 삭제 판정은 실행한 범위의 기수 안에서만 한다 (삭제하지 않고 표시만).
- 운영진이 처리할 레코드는 실행 이력의 unmapped_records에 남긴다:
  DB에 없는 기수(cohort_not_found), 기수가 바뀐 레코드(cohort_changed), 이름 오류(invalid_name).
  기수가 비었거나 별칭이 설정되지 않은 과정의 레코드는 대상이 아니라 건너뛴다.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.contexts.academy.domain.entities import Bootcamp, Cohort, RosterSyncRun, Student
from app.contexts.academy.domain.enums import RosterSyncScope, RosterSyncStatus, RosterSyncTrigger
from app.contexts.academy.domain.repositories import (
    BootcampRepository,
    CohortRepository,
    RosterSyncLock,
    RosterSyncRunRepository,
    StudentRepository,
)
from app.contexts.academy.domain.roster import (
    CohortLabel,
    RosterFieldMap,
    RosterRecord,
    UnmappedRecord,
    cohort_formula,
    interpret,
    prefixes_formula,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import AppError, BusinessRuleViolation, ConflictError, NotFoundError

logger = logging.getLogger(__name__)


class RosterSource(Protocol):
    """명단 원천 (Airtable 어댑터가 구현). (레코드 ID, 필드) 목록을 돌려준다."""

    async def fetch(self, formula: str, fields: list[str]) -> list[tuple[str, dict[str, Any]]]: ...


@dataclass(frozen=True, slots=True)
class _Scope:
    bootcamps: list[Bootcamp]  # 별칭이 있는 과정만
    cohorts: list[Cohort]  # 원천 삭제 판정 범위
    formula: str | None  # None이면 조회할 것이 없다


def _changes(student: Student) -> tuple[Any, ...]:
    return (
        student.name,
        student.phone_number,
        student.email,
        student.hrd_net_status,
        student.status,
        student.ended_at,
        student.end_reason,
        student.is_removed_in_source,
        student.source_fields,
    )


class RosterSyncService:
    def __init__(
        self,
        *,
        source: RosterSource,
        field_map: RosterFieldMap,
        bootcamps: BootcampRepository,
        cohorts: CohortRepository,
        students: StudentRepository,
        runs: RosterSyncRunRepository,
        lock: RosterSyncLock,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._source = source
        self._fields = field_map
        self._bootcamps = bootcamps
        self._cohorts = cohorts
        self._students = students
        self._runs = runs
        self._lock = lock
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def request(
        self,
        trigger: RosterSyncTrigger,
        scope_type: RosterSyncScope,
        *,
        bootcamp_id: uuid.UUID | None = None,
        cohort_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> RosterSyncRun:
        """락을 잡고 실행 이력(RUNNING)을 만든다. 실행(`execute`)이 끝나면 락을 놓는다.

        같은 범위가 이미 실행 중이면 409 `roster_sync_in_progress`.
        """
        if scope_type is RosterSyncScope.COHORT and cohort_id is not None:
            bootcamp_id = (await self._get_cohort(cohort_id)).bootcamp_id
        if not await self._lock.acquire(scope_type, bootcamp_id):
            raise ConflictError(
                "이미 진행 중인 명단 동기화가 있습니다. 끝난 뒤 다시 실행하세요.",
                code="roster_sync_in_progress",
            )
        try:
            async with self._uow:
                run = await self.create_run(
                    trigger, scope_type, bootcamp_id=bootcamp_id, cohort_id=cohort_id
                )
                if actor_id is not None:
                    await self._audit.record(
                        actor_user_id=actor_id,
                        action="academy.roster_sync.request",
                        target_type="roster_sync_run",
                        target_id=run.id,
                        after={"scope_type": scope_type.value},
                    )
        except BaseException:
            await self._lock.release(scope_type, bootcamp_id)
            raise
        return run

    async def run_scheduled(self) -> RosterSyncRun | None:
        """주기 동기화(전체). 다른 동기화가 실행 중이면 이번 주기는 건너뛴다."""
        try:
            run = await self.request(RosterSyncTrigger.SCHEDULED, RosterSyncScope.ALL)
        except ConflictError:
            logger.info("명단 동기화가 실행 중이라 이번 주기를 건너뜁니다.")
            return None
        return await self.execute(run.id)

    async def create_run(
        self,
        trigger: RosterSyncTrigger,
        scope_type: RosterSyncScope,
        *,
        bootcamp_id: uuid.UUID | None = None,
        cohort_id: uuid.UUID | None = None,
    ) -> RosterSyncRun:
        """실행 이력을 RUNNING으로 만든다. 대상 과정·기수가 동기화할 수 있는지 먼저 확인한다."""
        if scope_type is RosterSyncScope.COHORT and cohort_id is not None:
            cohort = await self._get_cohort(cohort_id)
            bootcamp_id = cohort.bootcamp_id
        if bootcamp_id is not None:
            await self._get_syncable_bootcamp(bootcamp_id)
        run = RosterSyncRun(
            trigger=trigger,
            scope_type=scope_type,
            bootcamp_id=bootcamp_id,
            cohort_id=cohort_id,
            started_at=self._clock.now(),
        )
        await self._runs.add(run)
        return run

    async def execute(self, run_id: uuid.UUID) -> RosterSyncRun:
        """실행한다. 실패하면 실행 이력에 오류를 남기고 예외를 올리지 않는다(워커용)."""
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError("동기화 실행을 찾을 수 없습니다.", code="roster_sync_run_not_found")
        if run.status is not RosterSyncStatus.RUNNING:
            # 이미 끝난 실행(작업 중복 전달).
            # 같은 범위의 새 실행이 잡은 락을 놓지 않도록 그대로 끝낸다
            return run
        try:
            return await self._execute(run)
        finally:
            await self._lock.release(run.scope_type, run.bootcamp_id)

    async def _execute(self, run: RosterSyncRun) -> RosterSyncRun:
        try:
            scope = await self._scope(run)
            fetched = (
                await self._source.fetch(scope.formula, self._fields.fetch_fields())
                if scope.formula
                else []
            )
            async with self._uow:
                await self._apply(run, scope, fetched)
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else f"{type(exc).__name__}: {exc}"
            logger.exception("명단 동기화 실패 (run=%s)", run.id)
            run.fail(now=self._clock.now(), error_message=message)
            await self._runs.save(run)
        return run

    # ------------------------------------------------------------------ 내부
    async def _scope(self, run: RosterSyncRun) -> _Scope:
        field = self._fields.cohort
        if run.scope_type is RosterSyncScope.COHORT:
            if run.cohort_id is None or run.bootcamp_id is None:  # RosterSyncRun이 보장한다
                raise ValueError("기수 동기화에 과정·기수가 없습니다.")
            cohort = await self._get_cohort(run.cohort_id)
            bootcamp = await self._get_syncable_bootcamp(run.bootcamp_id)
            prefix = bootcamp.airtable_cohort_prefix or ""
            label = CohortLabel(prefix=prefix, number=cohort.cohort_number)
            return _Scope([bootcamp], [cohort], cohort_formula(field, label))
        if run.scope_type is RosterSyncScope.BOOTCAMP:
            if run.bootcamp_id is None:  # RosterSyncRun이 보장한다
                raise ValueError("과정 동기화에 과정이 없습니다.")
            bootcamps = [await self._get_syncable_bootcamp(run.bootcamp_id)]
        else:
            bootcamps = [b for b in await self._bootcamps.list_all() if b.airtable_cohort_prefix]
        cohorts = [c for b in bootcamps for c in await self._cohorts.list_by_bootcamp(b.id)]
        prefixes = [b.airtable_cohort_prefix for b in bootcamps if b.airtable_cohort_prefix]
        return _Scope(bootcamps, cohorts, prefixes_formula(field, prefixes) if prefixes else None)

    async def _apply(
        self, run: RosterSyncRun, scope: _Scope, fetched: list[tuple[str, dict[str, Any]]]
    ) -> None:
        now = self._clock.now()
        bootcamp_by_prefix = {b.airtable_cohort_prefix: b for b in scope.bootcamps}
        all_cohorts = {
            (c.bootcamp_id, c.cohort_number): c
            for b in scope.bootcamps
            for c in await self._cohorts.list_by_bootcamp(b.id)
        }
        existing = {
            s.airtable_record_id: s
            for s in await self._students.list_by_record_ids(
                [record_id for record_id, _ in fetched]
            )
        }

        created: list[Student] = []
        changed: list[Student] = []
        unmapped: list[UnmappedRecord] = []
        seen: set[str] = set()
        for record_id, fields in fetched:
            seen.add(record_id)
            interpreted = interpret(record_id, fields, self._fields)
            if interpreted is None:
                continue
            if isinstance(interpreted, UnmappedRecord):
                unmapped.append(interpreted)
                continue
            bootcamp = bootcamp_by_prefix.get(interpreted.cohort.prefix)
            if bootcamp is None:
                continue  # 별칭이 설정되지 않은 과정 (범위 밖)
            cohort = all_cohorts.get((bootcamp.id, interpreted.cohort.number))
            student = existing.get(record_id)
            if cohort is None:
                unmapped.append(_unmapped(interpreted, "cohort_not_found", student))
                continue
            if student is None:
                created.append(self._new_student(interpreted, cohort, now))
                continue
            if student.cohort_id != cohort.id:
                unmapped.append(_unmapped(interpreted, "cohort_changed", student))
                continue
            before = _changes(student)
            identity_before = (student.name, student.phone_number)
            student.apply_source(
                name=interpreted.name,
                phone_number=interpreted.phone_number,
                email=interpreted.email,
                hrd_net_status=interpreted.hrd_status,
                source_fields=interpreted.source_fields,
                synced_at=now,
            )
            student.sync_enrollment(
                interpreted.enrollment_status,
                ended_on=interpreted.ended_on,
                reason=interpreted.status_text,
            )
            if _changes(student) != before:
                changed.append(student)
                if student.is_claimed and (student.name, student.phone_number) != identity_before:
                    await self._audit.record(
                        actor_user_id=None,
                        action="academy.student.source_identity_changed",
                        target_type="student",
                        target_id=student.id,
                        before={"name": identity_before[0], "phone_number": identity_before[1]},
                        after={"name": student.name, "phone_number": student.phone_number},
                    )

        removed = [
            s
            for s in await self._students.list_sourced_by_cohorts([c.id for c in scope.cohorts])
            if s.airtable_record_id not in seen and not s.is_removed_in_source
        ]
        for student in removed:
            student.mark_removed_in_source()

        await self._students.add_many(created)
        await self._students.save_many([*changed, *removed], now=now)
        run.succeed(
            now=now,
            fetched=len(fetched),
            upserted=len(created) + len(changed),
            removed=len(removed),
            unmapped_records=[u.as_json() for u in unmapped],
        )
        await self._runs.save(run)

    def _new_student(self, record: RosterRecord, cohort: Cohort, now: Any) -> Student:
        student = Student(
            cohort_id=cohort.id,
            airtable_record_id=record.record_id,
            name=record.name,
            phone_number=record.phone_number,
            email=record.email,
            hrd_net_status=record.hrd_status,
            source_fields=record.source_fields,
            synced_at=now,
            enrolled_at=cohort.start_date,
        )
        student.sync_enrollment(
            record.enrollment_status, ended_on=record.ended_on, reason=record.status_text
        )
        return student

    async def _get_cohort(self, cohort_id: uuid.UUID) -> Cohort:
        cohort = await self._cohorts.get(cohort_id)
        if cohort is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")
        return cohort

    async def _get_syncable_bootcamp(self, bootcamp_id: uuid.UUID) -> Bootcamp:
        bootcamp = await self._bootcamps.get(bootcamp_id)
        if bootcamp is None:
            raise NotFoundError("운영과정을 찾을 수 없습니다.", code="bootcamp_not_found")
        if not bootcamp.airtable_cohort_prefix:
            raise BusinessRuleViolation(
                "Airtable 기수 별칭이 설정되지 않은 과정입니다.", code="airtable_prefix_missing"
            )
        return bootcamp


def _unmapped(record: RosterRecord, reason: str, student: Student | None) -> UnmappedRecord:
    return UnmappedRecord(
        record_id=record.record_id,
        name=record.name,
        cohort_label=str(record.cohort),
        reason=reason,
        existing_student_id=student.id if student else None,
    )

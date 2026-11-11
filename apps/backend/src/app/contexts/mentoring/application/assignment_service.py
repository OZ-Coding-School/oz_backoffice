"""기수 멘토 배정 관리 (decisions A35, 권한 mentoring.assignment.manage).

- 계약과 별개로 운영진이 등록·수정·비활성화(삭제)·재활성화한다.
- 활성 배정은 (멘토, 기수)당 하나 → 409 `assignment_already_exists` (유형 구분 없음, A41).
- 시작일은 기수 기간 안, 종료일은 선택. 비활성 멘토는 새 배정·재활성화 불가 → 422 `mentor_inactive`.
- 배정 생성·재활성화는 멘토 행을 잠가 멘토 비활성화와 겹치지 않게 한다.
- 매일 00:00 KST 작업이 종료일이 지난 배정을 비활성화한다(EXPIRED, 멱등).
모든 변경은 감사 로그를 남긴다.
"""

import dataclasses
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol

from app.contexts.academy.domain.entities import Cohort
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import CohortMentorDeactivationReason
from app.contexts.mentoring.domain.repositories import CohortMentorRepository
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.time import business_date

TARGET = "cohort_mentor"


class CohortLookup(Protocol):
    """academy `AcademyCatalog`."""

    async def get_cohort(self, cohort_id: uuid.UUID) -> Cohort | None: ...


class MentorDirectory(Protocol):
    """educator `MentorQueries`."""

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...
    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]: ...
    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def set_active(self, mentor: Mentor, active: bool) -> None: ...


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def snapshot(assignment: CohortMentor) -> dict[str, Any]:
    skip = {"id", "created_at", "updated_at"}
    return {
        f.name: _jsonable(getattr(assignment, f.name))
        for f in dataclasses.fields(assignment)
        if f.init and f.name not in skip
    }


async def record_change(
    audit: AuditRecorder,
    actor_id: uuid.UUID | None,
    action: str,
    after: CohortMentor,
    before: dict[str, Any] | None,
) -> None:
    await audit.record(
        actor_user_id=actor_id,
        action=f"mentoring.assignment.{action}",
        target_type=TARGET,
        target_id=after.id,
        before=before,
        after=snapshot(after),
    )


async def ensure_no_active_duplicate(
    assignments: CohortMentorRepository, assignment: CohortMentor
) -> None:
    active = await assignments.find_active(assignment.mentor_id, assignment.cohort_id)
    if active is not None and active.id != assignment.id:
        raise ConflictError(
            "이 기수에 이미 활성 배정된 멘토입니다.", code="assignment_already_exists"
        )


def ensure_mentor_active(mentor: Mentor | None) -> Mentor:
    if mentor is None:
        raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
    if not mentor.is_active:
        raise BusinessRuleViolation(
            "비활성화된 멘토는 기수에 배정할 수 없습니다.", code="mentor_inactive"
        )
    return mentor


class CohortMentorService:
    def __init__(
        self,
        *,
        assignments: CohortMentorRepository,
        mentors: MentorDirectory,
        cohorts: CohortLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._assignments = assignments
        self._mentors = mentors
        self._cohorts = cohorts
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 조회
    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]:
        await self._cohort(cohort_id)
        return await self._assignments.list_by_cohort(cohort_id, include_inactive=include_inactive)

    async def list_mine(self, user_id: uuid.UUID, *, include_inactive: bool) -> list[CohortMentor]:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        return await self._assignments.list_by_mentor(mentor.id, include_inactive=include_inactive)

    # ------------------------------------------------------------------ 변경
    async def create(
        self, cohort_id: uuid.UUID, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> CohortMentor:
        cohort = await self._cohort(cohort_id)
        assignment = CohortMentor(cohort_id=cohort_id, **values)
        assignment.ensure_starts_within(cohort.start_date, cohort.end_date)
        async with self._uow:
            ensure_mentor_active(await self._mentors.lock(assignment.mentor_id))
            await ensure_no_active_duplicate(self._assignments, assignment)
            await self._assignments.add(assignment)
            await record_change(self._audit, actor_id, "create", assignment, None)
        return await self._get(cohort_id, assignment.id)

    async def update(
        self,
        cohort_id: uuid.UUID,
        assignment_id: uuid.UUID,
        values: dict[str, Any],
        *,
        actor_id: uuid.UUID,
    ) -> CohortMentor:
        """기간·정산 조건만 바꾼다. 정산은 마감 때 값을 저장하므로 지난 정산에 영향이 없다."""
        cohort = await self._cohort(cohort_id)
        async with self._uow:
            current = await self._get(cohort_id, assignment_id)
            updated = current.revised(values)
            updated.ensure_starts_within(cohort.start_date, cohort.end_date)
            await self._assignments.save(updated)
            await record_change(self._audit, actor_id, "update", updated, snapshot(current))
        return await self._get(cohort_id, assignment_id)

    async def deactivate(
        self, cohort_id: uuid.UUID, assignment_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> CohortMentor:
        """삭제 = 비활성화 (기록 보존)."""
        async with self._uow:
            assignment = await self._get(cohort_id, assignment_id)
            before = snapshot(assignment)
            assignment.deactivate(CohortMentorDeactivationReason.MANUAL, now=self._clock.now())
            await self._assignments.save(assignment)
            await record_change(self._audit, actor_id, "deactivate", assignment, before)
        return assignment

    async def reactivate(
        self, cohort_id: uuid.UUID, assignment_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> CohortMentor:
        async with self._uow:
            assignment = await self._get(cohort_id, assignment_id)
            ensure_mentor_active(await self._mentors.lock(assignment.mentor_id))
            before = snapshot(assignment)
            assignment.reactivate(today=business_date(self._clock.now()))
            await ensure_no_active_duplicate(self._assignments, assignment)
            await self._assignments.save(assignment)
            await record_change(self._audit, actor_id, "reactivate", assignment, before)
        return assignment

    async def expire_ended(self) -> int:
        """종료일이 지난 활성 배정을 비활성화한다 (매일 00:00 KST, 멱등)."""
        now = self._clock.now()
        async with self._uow:
            expired = await self._assignments.list_expired(business_date(now))
            for assignment in expired:
                before = snapshot(assignment)
                assignment.deactivate(CohortMentorDeactivationReason.EXPIRED, now=now)
                await self._assignments.save(assignment)
                await record_change(self._audit, None, "expire", assignment, before)
        return len(expired)

    # ------------------------------------------------------------------ 내부
    async def _cohort(self, cohort_id: uuid.UUID) -> Cohort:
        cohort = await self._cohorts.get_cohort(cohort_id)
        if cohort is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")
        return cohort

    async def _get(self, cohort_id: uuid.UUID, assignment_id: uuid.UUID) -> CohortMentor:
        assignment = await self._assignments.get(assignment_id)
        if assignment is None or assignment.cohort_id != cohort_id:
            raise NotFoundError("기수 멘토 배정을 찾을 수 없습니다.", code="assignment_not_found")
        return assignment

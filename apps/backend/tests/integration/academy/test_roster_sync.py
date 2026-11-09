from datetime import date
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.academy.application.cohort_master_sync import CohortMasterSync
from app.contexts.academy.application.roster_queries import RosterQueries
from app.contexts.academy.application.roster_sync import RosterSyncService
from app.contexts.academy.domain.cohort_source import CohortFieldMap
from app.contexts.academy.domain.entities import Bootcamp, Cohort, Student
from app.contexts.academy.domain.enums import (
    EnrollmentStatus,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
)
from app.contexts.academy.domain.roster import RosterFieldMap
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.academy.infrastructure.roster_sync_lock import RedisRosterSyncLock
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.fakes.roster import FakeRosterSource

pytestmark = pytest.mark.integration


def service(
    source: FakeRosterSource,
    lock: RedisRosterSyncLock | None = None,
    cohort_source: FakeRosterSource | None = None,
) -> RosterSyncService:
    clock = SystemClock()
    return RosterSyncService(
        source=source,
        field_map=RosterFieldMap(),
        cohort_source=cohort_source or FakeRosterSource(),
        master=CohortMasterSync(
            field_map=CohortFieldMap(),
            hrd_bootcamps=TortoiseHrdNetBootcampRepository(),
            hrd_cohorts=TortoiseHrdNetBootcampCohortRepository(),
            bootcamps=TortoiseBootcampRepository(),
            cohorts=TortoiseCohortRepository(),
        ),
        cohort_field_map=CohortFieldMap(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
        students=TortoiseStudentRepository(),
        runs=TortoiseRosterSyncRunRepository(),
        lock=lock or RedisRosterSyncLock(FakeAsyncRedis(decode_responses=True)),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


async def _bootcamp_with_prefix(prefix: str, *numbers: int) -> tuple[Bootcamp, list[Cohort]]:
    first = await create_cohort(cohort_number=numbers[0])
    bootcamps = TortoiseBootcampRepository()
    bootcamp = await bootcamps.get(first.bootcamp_id)
    assert bootcamp is not None
    bootcamp.airtable_cohort_prefix = prefix
    await bootcamps.save(bootcamp)
    cohorts = [first]
    for number in numbers[1:]:
        cohort = Cohort(
            hrd_net_cohort_id=first.hrd_net_cohort_id,
            bootcamp_id=bootcamp.id,
            cohort_number=number,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 6, 30),
        )
        await TortoiseCohortRepository().add(cohort)
        cohorts.append(cohort)
    return bootcamp, cohorts


def record(name: str, label: str, **extra: Any) -> dict[str, Any]:
    return {
        "이름": name,
        "전화번호": "010-1234-5678",
        "기수": [label],
        "상태": "수강중",
        "HRD상태": "수강중",
        **extra,
    }


async def _run(svc: RosterSyncService, scope: RosterSyncScope, **ids: Any) -> Any:
    run = await svc.create_run(RosterSyncTrigger.MANUAL, scope, **ids)
    return await svc.execute(run.id)


async def _students(cohort: Cohort) -> dict[str, Student]:
    rows = await TortoiseStudentRepository().list_sourced_by_cohorts([cohort.id])
    return {s.airtable_record_id or "": s for s in rows}


async def test_full_sync_creates_updates_and_is_idempotent() -> None:
    bootcamp, (c1, c2) = await _bootcamp_with_prefix("헬스케어", 1, 2)
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "헬스케어 1기"))
    source.put(
        "rec2",
        **record(
            "이오즈", "헬스케어 2기", 상태="하차", HRD상태="중도탈락", 중도탈락일="2026-12-01"
        ),
    )
    source.put("rec3", **record("박오즈", "헬스케어 9기"))  # DB에 없는 기수
    source.put("rec4", **record("최오즈", "프론트 1기"))  # 별칭이 설정되지 않은 과정 → 범위 밖
    svc = service(source)

    run = await _run(svc, RosterSyncScope.ALL)

    assert run.status is RosterSyncStatus.SUCCEEDED, run.error_message
    assert source.formulas == ["FIND('헬스케어 ', ARRAYJOIN({기수}))=1"]
    assert (run.fetched_count, run.upserted_count, run.removed_count, run.unmapped_count) == (
        3,
        2,
        0,
        1,
    )
    assert run.unmapped_records[0]["reason"] == "cohort_not_found"
    first = (await _students(c1))["rec1"]
    assert (first.name, first.phone_number, first.status, first.user_id, first.enrolled_at) == (
        "김오즈",
        "01012345678",
        EnrollmentStatus.ENROLLED,
        None,
        c1.start_date,
    )
    dropped = (await _students(c2))["rec2"]
    assert (dropped.status, dropped.hrd_net_status, dropped.ended_at, dropped.end_reason) == (
        EnrollmentStatus.DROPPED,
        StudentStatus.DROPPED_OUT,
        None,  # 중도탈락일이 등록일(2027-01-01)보다 빨라 비움
        "하차",
    )

    again = await _run(svc, RosterSyncScope.ALL)
    assert (again.upserted_count, again.removed_count) == (0, 0)  # 멱등
    assert bootcamp.id


async def test_status_follows_airtable_but_keeps_transfer() -> None:
    _, (c1,) = await _bootcamp_with_prefix("BD", 1)
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "BD 1기"))
    source.put("rec2", **record("이오즈", "BD 1기"))
    svc = service(source)
    await _run(svc, RosterSyncScope.ALL)
    students = TortoiseStudentRepository()
    moved = (await _students(c1))["rec2"]
    moved.end(EnrollmentStatus.TRANSFERRED, on=date(2026, 12, 1))
    await students.save(moved)

    source.put("rec1", **record("김오즈", "BD 1기", 상태="정상수료", 훈련종료일="2027-04-30"))
    source.put("rec2", **record("이오즈", "BD 1기", 상태="정상수료"))
    run = await _run(svc, RosterSyncScope.ALL)

    synced = await _students(c1)
    assert (synced["rec1"].status, synced["rec1"].ended_at) == (
        EnrollmentStatus.COMPLETED,
        date(2027, 4, 30),
    )
    assert synced["rec2"].status is EnrollmentStatus.TRANSFERRED
    assert run.upserted_count == 2  # rec2는 원천 필드(source_fields)가 바뀌었다


async def test_cohort_scope_only_touches_its_cohort() -> None:
    bootcamp, (c1, c2) = await _bootcamp_with_prefix("게임개발", 1, 2)
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "게임개발 1기"))
    source.put("rec2", **record("이오즈", "게임개발 2기"))
    svc = service(source)
    await _run(svc, RosterSyncScope.ALL)

    del source.records["rec2"]  # 2기 레코드가 원천에서 사라짐
    del source.records["rec1"]  # 1기 레코드도 사라짐
    run = await _run(svc, RosterSyncScope.COHORT, cohort_id=c1.id)

    assert source.formulas[-1] == "ARRAYJOIN({기수})='게임개발 1기'"
    assert run.removed_count == 1
    assert (await _students(c1))["rec1"].is_removed_in_source
    assert not (await _students(c2))["rec2"].is_removed_in_source  # 다른 기수는 판정하지 않는다

    source.put("rec1", **record("김오즈", "게임개발 1기"))
    await _run(svc, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id)
    assert not (await _students(c1))["rec1"].is_removed_in_source  # 다시 나타나면 되돌린다
    assert (await _students(c2))["rec2"].is_removed_in_source


async def test_cohort_change_and_claimed_identity_change() -> None:
    _, (c1, c2) = await _bootcamp_with_prefix("UD", 1, 2)
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "UD 1기"))
    source.put("rec2", **record("이오즈", "UD 1기"))
    svc = service(source)
    await _run(svc, RosterSyncScope.ALL)
    claimed = (await _students(c1))["rec2"]
    user = make_user()
    await TortoiseUserRepository().add(user)
    claimed.claim(user.id)
    await TortoiseStudentRepository().save(claimed)

    source.put("rec1", **record("김오즈", "UD 2기"))  # 기수가 바뀜 → 자동으로 옮기지 않음
    source.put("rec2", **record("이오즈", "UD 1기", 전화번호="010-9999-0000"))
    run = await _run(svc, RosterSyncScope.ALL)

    assert [(u["airtable_record_id"], u["reason"]) for u in run.unmapped_records] == [
        ("rec1", "cohort_changed")
    ]
    assert "rec1" in await _students(c1)
    assert await _students(c2) == {}
    log = await AuditLogModel.get(target_id=claimed.id)
    assert (log.action, log.after) == (
        "academy.student.source_identity_changed",
        {"name": "이오즈", "phone_number": "01099990000"},
    )


async def test_failures_are_recorded_on_the_run() -> None:
    bootcamp, _ = await _bootcamp_with_prefix("MVP", 1)
    source = FakeRosterSource()
    source.fail_with = RuntimeError("airtable down")
    run = await _run(service(source), RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id)
    assert run.status is RosterSyncStatus.FAILED
    assert "airtable down" in (run.error_message or "")
    loaded = await TortoiseRosterSyncRunRepository().get(run.id)
    assert loaded is not None
    assert loaded.status is RosterSyncStatus.FAILED


async def test_bootcamp_without_prefix_fails_the_run() -> None:
    cohort = await create_cohort()
    run = await _run(service(FakeRosterSource()), RosterSyncScope.COHORT, cohort_id=cohort.id)
    assert run.status is RosterSyncStatus.FAILED
    assert "Airtable 기수 별칭" in (run.error_message or "")


async def test_all_scope_without_prefixes_does_nothing() -> None:
    await create_cohort()
    source = FakeRosterSource()
    run = await _run(service(source), RosterSyncScope.ALL)
    assert (run.status, run.fetched_count, source.formulas) == (RosterSyncStatus.SUCCEEDED, 0, [])


async def test_request_locks_scope_until_execution_ends(fake_redis: FakeAsyncRedis) -> None:
    bootcamp, (c1,) = await _bootcamp_with_prefix("1인창업", 1)
    other_bootcamp, _ = await _bootcamp_with_prefix("CEO", 1)
    lock = RedisRosterSyncLock(fake_redis)
    svc = service(FakeRosterSource(), lock)
    actor = make_user()
    await TortoiseUserRepository().add(actor)

    run = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.COHORT, cohort_id=c1.id, actor_id=actor.id
    )
    assert run.bootcamp_id == bootcamp.id
    for scope, ids in (
        (RosterSyncScope.BOOTCAMP, {"bootcamp_id": bootcamp.id}),  # 같은 과정
        (RosterSyncScope.ALL, {}),  # 전체는 다른 실행이 있으면 막힌다
    ):
        with pytest.raises(ConflictError) as exc:
            await svc.request(RosterSyncTrigger.MANUAL, scope, **ids)
        assert exc.value.code == "roster_sync_in_progress"
    # 다른 과정은 동시에 실행할 수 있다
    other = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=other_bootcamp.id
    )
    await svc.execute(other.id)

    await svc.execute(run.id)
    again = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
    )
    assert again.status is RosterSyncStatus.RUNNING
    log = await AuditLogModel.get(target_id=run.id)
    assert log.action == "academy.roster_sync.request"


async def test_scheduled_sync_skips_while_another_runs(fake_redis: FakeAsyncRedis) -> None:
    bootcamp, _ = await _bootcamp_with_prefix("풀스택", 1)
    lock = RedisRosterSyncLock(fake_redis)
    svc = service(FakeRosterSource(), lock)
    manual = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
    )

    assert await svc.run_scheduled() is None
    await svc.execute(manual.id)
    scheduled = await svc.run_scheduled()
    assert scheduled is not None
    assert (scheduled.trigger, scheduled.status) == (
        RosterSyncTrigger.SCHEDULED,
        RosterSyncStatus.SUCCEEDED,
    )


async def test_duplicate_delivery_does_not_release_new_lock(fake_redis: FakeAsyncRedis) -> None:
    bootcamp, _ = await _bootcamp_with_prefix("AI리더", 1)
    lock = RedisRosterSyncLock(fake_redis)
    svc = service(FakeRosterSource(), lock)
    first = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
    )
    await svc.execute(first.id)
    await svc.request(RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id)

    await svc.execute(first.id)  # 같은 작업이 한 번 더 전달됨

    with pytest.raises(ConflictError):  # 새 실행의 락은 그대로
        await svc.request(
            RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
        )


async def test_queries_and_abort(fake_redis: FakeAsyncRedis) -> None:
    bootcamp, (c1,) = await _bootcamp_with_prefix("디자이너", 1)
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "디자이너 1기"))
    source.put("rec2", **record("이오즈", "디자이너 1기"))
    lock = RedisRosterSyncLock(fake_redis)
    svc = service(source, lock)
    full = await _run(svc, RosterSyncScope.ALL)
    del source.records["rec2"]
    partial = await _run(svc, RosterSyncScope.COHORT, cohort_id=c1.id)
    queries = RosterQueries(
        runs=TortoiseRosterSyncRunRepository(),
        students=TortoiseStudentRepository(),
        cohorts=TortoiseCohortRepository(),
    )

    assert [r.id for r in await queries.recent_runs(before=None, limit=10)] == [partial.id, full.id]
    assert [r.id for r in await queries.recent_runs(before=partial.id, limit=10)] == [full.id]
    latest = await queries.latest_unmapped()
    assert latest is not None
    assert latest.id == full.id  # 전체 동기화 기준
    active = await queries.cohort_students(c1.id, claimed=None, include_removed=False)
    assert [s.airtable_record_id for s in active] == ["rec1"]
    every = await queries.cohort_students(c1.id, claimed=False, include_removed=True)
    assert len(every) == 2
    assert await queries.cohort_students(c1.id, claimed=True, include_removed=True) == []

    run = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
    )
    await svc.abort(run.id, reason="작업 전달 실패")
    aborted = await queries.get_run(run.id)
    assert (aborted.status, aborted.error_message) == (RosterSyncStatus.FAILED, "작업 전달 실패")
    again = await svc.request(
        RosterSyncTrigger.MANUAL, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp.id
    )
    assert again.status is RosterSyncStatus.RUNNING  # 락이 풀렸다


async def test_full_sync_builds_cohorts_from_airtable_then_students() -> None:
    cohort_source = FakeRosterSource()
    cohort_source.put(
        "recC1",
        **{
            "캠프기수": "헬스케어 1기",
            "과정코드": "AH",
            "훈련과정ID": "AIG20250000501719",
            "훈련과정명": "헬스케어 과정",
            "훈련회차": "1",
            "훈련시작일": "2025-01-01",
            "훈련종료일": "2025-06-30",
            "과정 진행상태": "취업 산정 종료",
        },
    )
    source = FakeRosterSource()
    source.put("rec1", **record("김오즈", "헬스케어 1기"))
    svc = service(source, cohort_source=cohort_source)

    run = await _run(svc, RosterSyncScope.ALL)

    assert run.status is RosterSyncStatus.SUCCEEDED, run.error_message
    assert cohort_source.formulas == [None]
    cohort = await TortoiseCohortRepository().get_by_airtable_record_id("recC1")
    assert cohort is not None
    assert "rec1" in await _students(cohort)

    bootcamp_run = await _run(svc, RosterSyncScope.BOOTCAMP, bootcamp_id=cohort.bootcamp_id)
    assert bootcamp_run.status is RosterSyncStatus.SUCCEEDED
    assert cohort_source.formulas[-1] == "{과정코드}='AH'"

from datetime import date
from typing import Any

import pytest

from app.contexts.academy.application.roster_sync import RosterSyncService
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
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.fakes.roster import FakeRosterSource

pytestmark = pytest.mark.integration


def service(source: FakeRosterSource) -> RosterSyncService:
    clock = SystemClock()
    return RosterSyncService(
        source=source,
        field_map=RosterFieldMap(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
        students=TortoiseStudentRepository(),
        runs=TortoiseRosterSyncRunRepository(),
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


async def test_bootcamp_without_prefix_cannot_be_synced() -> None:
    cohort = await create_cohort()
    with pytest.raises(BusinessRuleViolation) as exc:
        await service(FakeRosterSource()).create_run(
            RosterSyncTrigger.MANUAL, RosterSyncScope.COHORT, cohort_id=cohort.id
        )
    assert exc.value.code == "airtable_prefix_missing"


async def test_all_scope_without_prefixes_does_nothing() -> None:
    await create_cohort()
    source = FakeRosterSource()
    run = await _run(service(source), RosterSyncScope.ALL)
    assert (run.status, run.fetched_count, source.formulas) == (RosterSyncStatus.SUCCEEDED, 0, [])

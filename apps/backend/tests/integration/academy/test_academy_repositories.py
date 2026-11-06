import uuid
from datetime import UTC, date, datetime

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.domain.entities import RosterSyncRun, Student
from app.contexts.academy.domain.enums import (
    CohortStatus,
    EnrollmentStatus,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
)
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from tests.factories.academy import create_cohort, make_student
from tests.factories.identity import make_user

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


async def test_cohort_hierarchy_round_trip_and_lookup() -> None:
    cohort = await create_cohort(code="ah", cohort_number=3)
    cohorts = TortoiseCohortRepository()

    bootcamp = await TortoiseBootcampRepository().get_by_code("AH")
    assert bootcamp is not None
    assert await cohorts.get_by_number(bootcamp.id, 3) == cohort
    assert [c.id for c in await cohorts.list_by_bootcamp(bootcamp.id)] == [cohort.id]

    loaded = await cohorts.get(cohort.id)
    assert loaded is not None
    loaded.change_status(CohortStatus.ONGOING)
    await cohorts.save(loaded)
    reloaded = await cohorts.get(cohort.id)
    assert reloaded is not None
    assert reloaded.status is CohortStatus.ONGOING


async def test_cohort_number_is_unique_per_bootcamp() -> None:
    cohort = await create_cohort(code="AL", cohort_number=1)
    duplicate = await create_cohort(code="GM", cohort_number=1)
    duplicate.bootcamp_id = cohort.bootcamp_id
    with pytest.raises(IntegrityError):
        await TortoiseCohortRepository().save(duplicate)


async def test_student_enrollment_is_unique_per_user_and_cohort() -> None:
    user = make_user()
    await TortoiseUserRepository().add(user)
    first, second = await create_cohort(), await create_cohort()
    students = TortoiseStudentRepository()

    def enroll(cohort_id: uuid.UUID) -> Student:
        return make_student(user_id=user.id, cohort_id=cohort_id)

    await students.add(enroll(first.id))
    await students.add(enroll(second.id))  # 다른 기수 재수강은 허용
    assert len(await students.list_by_user(user.id)) == 2
    with pytest.raises(IntegrityError):
        await students.add(enroll(first.id))

    student = await students.get_by_user_and_cohort(user.id, first.id)
    assert student is not None
    student.end(EnrollmentStatus.COMPLETED, on=date(2027, 4, 30))
    await students.save(student)
    saved = await students.get(student.id)
    assert saved is not None
    assert saved.status is EnrollmentStatus.COMPLETED


async def test_unclaimed_students_round_trip_and_unique_record_id() -> None:
    cohort = await create_cohort()
    students = TortoiseStudentRepository()
    # 가입 전 수강생 여러 명이 같은 기수에 있어도 (user, cohort) 유니크에 걸리지 않는다
    first = make_student(cohort_id=cohort.id, source_fields={"기수": "AH1"})
    await students.add(first)
    await students.add(make_student(cohort_id=cohort.id))

    loaded = await students.get_by_record_id(first.airtable_record_id or "")
    assert loaded is not None
    assert (loaded.user_id, loaded.source_fields) == (None, {"기수": "AH1"})
    assert await students.get_by_record_id("recUnknown") is None

    with pytest.raises(IntegrityError):
        await students.add(
            make_student(cohort_id=cohort.id, airtable_record_id=first.airtable_record_id)
        )


async def test_claimable_candidates_exclude_removed_ended_and_claimed() -> None:
    cohort, other = await create_cohort(), await create_cohort()
    students = TortoiseStudentRepository()
    same = {"name": "김오즈", "phone_number": "01012345678"}
    target = make_student(cohort_id=cohort.id, **same)
    await students.add(target)
    await students.add(make_student(cohort_id=cohort.id, is_removed_in_source=True, **same))
    ended = make_student(cohort_id=other.id, **same)
    ended.end(EnrollmentStatus.DROPPED, on=date(2026, 12, 1))
    await students.add(ended)
    await students.add(make_student(cohort_id=cohort.id, name="김오즈", phone_number="01000000000"))

    candidates = await students.find_claimable_by_name_and_phone("김오즈", "01012345678")
    assert [s.id for s in candidates] == [target.id]

    user = make_user()
    await TortoiseUserRepository().add(user)
    target.claim(user.id)
    await students.save(target)
    assert await students.find_claimable_by_name_and_phone("김오즈", "01012345678") == []
    assert await students.get_by_user_and_cohort(user.id, cohort.id) is not None


async def test_roster_sync_run_round_trip() -> None:
    cohort = await create_cohort()
    runs = TortoiseRosterSyncRunRepository()
    run = RosterSyncRun(
        trigger=RosterSyncTrigger.MANUAL,
        scope_type=RosterSyncScope.COHORT,
        bootcamp_id=cohort.bootcamp_id,
        cohort_id=cohort.id,
        started_at=NOW,
    )
    await runs.add(run)
    unmapped = [{"airtable_record_id": "recX", "name": "김오즈", "cohort": "AH99"}]
    run.succeed(now=NOW, fetched=5, upserted=4, removed=0, unmapped_records=unmapped)
    await runs.save(run)
    loaded = await runs.get(run.id)
    assert loaded is not None
    assert loaded.status is RosterSyncStatus.SUCCEEDED
    assert (loaded.upserted_count, loaded.unmapped_count) == (4, 1)
    assert loaded.unmapped_records == unmapped


@pytest.mark.parametrize(
    ("sql", "constraint"),
    [
        ("UPDATE cohorts SET start_date = '2027-12-31'", "check_cohort_period"),
        ("UPDATE cohorts SET status = 'UNKNOWN'", "check_cohorts_status"),
        (
            "INSERT INTO roster_sync_runs (id, trigger, scope_type, started_at, cohort_id) "
            "VALUES (gen_random_uuid(), 'MANUAL', 'ALL', now(), (SELECT id FROM cohorts LIMIT 1))",
            "check_roster_sync_scope",
        ),
        (
            "INSERT INTO students (id, cohort_id, name, phone_number, hrd_net_status, "
            "enrolled_at) VALUES (gen_random_uuid(), (SELECT id FROM cohorts LIMIT 1), '김', "
            "'0212345678', 'TRAINING', '2026-11-01')",
            "check_students_phone_number",
        ),
    ],
)
async def test_db_check_constraints(sql: str, constraint: str) -> None:
    await create_cohort()
    with pytest.raises(IntegrityError, match=constraint):
        await connections.get("default").execute_query(sql)

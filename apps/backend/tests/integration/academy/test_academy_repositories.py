from datetime import UTC, date, datetime

import pytest
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError

from app.contexts.academy.domain.entities import RosterSyncRun, Student
from app.contexts.academy.domain.enums import (
    CohortStatus,
    EnrollmentStatus,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
)
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
    TortoiseStudentRosterRepository,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from tests.factories.academy import create_cohort, make_roster
from tests.factories.identity import make_user

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("db")]

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

    def enroll(cohort_id: object) -> Student:
        return Student(
            user_id=user.id,
            cohort_id=cohort_id,  # type: ignore[arg-type]
            hrd_net_status=StudentStatus.TRAINING,
            enrolled_at=date(2026, 11, 1),
        )

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


async def test_roster_matching_candidates_exclude_unmapped_removed_and_matched() -> None:
    cohort = await create_cohort()
    rosters = TortoiseStudentRosterRepository()
    target = make_roster(name="김오즈", phone_number="01012345678", cohort_id=cohort.id)
    await rosters.add(target)
    await rosters.add(make_roster(name="김오즈", phone_number="01012345678", cohort_id=None))
    await rosters.add(
        make_roster(
            name="김오즈",
            phone_number="01012345678",
            cohort_id=cohort.id,
            is_removed_in_source=True,
        )
    )

    candidates = await rosters.find_unmatched_by_name_and_phone("김오즈", "01012345678")
    assert [r.id for r in candidates] == [target.id]

    user = make_user()
    await TortoiseUserRepository().add(user)
    student = Student(
        user_id=user.id,
        cohort_id=cohort.id,
        hrd_net_status=StudentStatus.TRAINING,
        enrolled_at=date(2026, 11, 1),
    )
    await TortoiseStudentRepository().add(student)
    target.match(student.id)
    await rosters.save(target)
    assert await rosters.find_unmatched_by_name_and_phone("김오즈", "01012345678") == []
    loaded = await rosters.get_by_record_id(target.airtable_record_id)
    assert loaded is not None
    assert loaded.matched_student_id == student.id


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
    run.succeed(now=NOW, fetched=5, upserted=5, removed=0, unmapped=0)
    await runs.save(run)
    loaded = await runs.get(run.id)
    assert loaded is not None
    assert loaded.status is RosterSyncStatus.SUCCEEDED
    assert loaded.upserted_count == 5


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
            "INSERT INTO student_rosters (id, airtable_record_id, name, phone_number, "
            "source_fields, synced_at) VALUES (gen_random_uuid(), 'recX', '김', '0212345678', "
            "'{}', now())",
            "check_student_rosters_phone_number",
        ),
    ],
)
async def test_db_check_constraints(sql: str, constraint: str) -> None:
    await create_cohort()
    with pytest.raises(IntegrityError, match=constraint):
        await Tortoise.get_connection("default").execute_query(sql)

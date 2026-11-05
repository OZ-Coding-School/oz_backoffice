from datetime import UTC, date, datetime

import pytest

from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
    RosterSyncRun,
    Student,
    StudentRoster,
)
from app.contexts.academy.domain.enums import (
    EnrollmentStatus,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
D1, D2 = date(2026, 11, 1), date(2027, 4, 30)


def test_bootcamp_code_is_uppercased_and_validated() -> None:
    bootcamp = Bootcamp(hrd_net_bootcamp_id=new_id(), name=" 백엔드 ", code=" ah ")
    assert (bootcamp.name, bootcamp.code) == ("백엔드", "AH")
    with pytest.raises(BusinessRuleViolation):
        Bootcamp(hrd_net_bootcamp_id=new_id(), name="x", code="A-H")


def test_hrd_entities_validate_numbers_and_periods() -> None:
    with pytest.raises(BusinessRuleViolation):
        HrdNetBootcamp(name="과정", total_train_fee=-1)
    with pytest.raises(BusinessRuleViolation):
        HrdNetBootcampCohort(hrd_net_bootcamp_id=new_id(), cohort_number=0)
    with pytest.raises(BusinessRuleViolation):
        HrdNetBootcampCohort(
            hrd_net_bootcamp_id=new_id(), cohort_number=1, train_start_date=D2, train_end_date=D1
        )


def test_cohort_period_must_be_ordered() -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        Cohort(
            hrd_net_cohort_id=new_id(),
            bootcamp_id=new_id(),
            cohort_number=1,
            start_date=D2,
            end_date=D1,
        )
    assert exc.value.code == "invalid_cohort"


def test_student_end_transitions() -> None:
    student = Student(
        user_id=new_id(), cohort_id=new_id(), hrd_net_status=StudentStatus.TRAINING, enrolled_at=D1
    )
    assert student.is_enrolled
    with pytest.raises(BusinessRuleViolation):
        student.end(EnrollmentStatus.ENROLLED, on=D2)
    with pytest.raises(BusinessRuleViolation):
        student.end(EnrollmentStatus.DROPPED, on=date(2026, 10, 1))

    student.end(EnrollmentStatus.DROPPED, on=D2, reason="개인 사정")
    assert (student.status, student.ended_at, student.end_reason) == (
        EnrollmentStatus.DROPPED,
        D2,
        "개인 사정",
    )
    with pytest.raises(BusinessRuleViolation) as exc:
        student.end(EnrollmentStatus.COMPLETED, on=D2)
    assert exc.value.code == "student_not_enrolled"


def test_roster_normalizes_and_matches_once() -> None:
    roster = StudentRoster(
        airtable_record_id="rec00000000000001",
        name=" 김오즈 ",
        phone_number="010-1234-5678",
        email=" Kim@Gmail.com ",
        synced_at=NOW,
    )
    assert (roster.name, roster.phone_number, roster.email) == (
        "김오즈",
        "01012345678",
        "kim@gmail.com",
    )
    student_id = new_id()
    roster.match(student_id)
    assert roster.is_matched
    with pytest.raises(BusinessRuleViolation) as exc:
        roster.match(new_id())
    assert exc.value.code == "roster_already_matched"


@pytest.mark.parametrize(
    ("scope", "bootcamp", "cohort", "valid"),
    [
        (RosterSyncScope.ALL, False, False, True),
        (RosterSyncScope.ALL, True, False, False),
        (RosterSyncScope.BOOTCAMP, True, False, True),
        (RosterSyncScope.BOOTCAMP, True, True, False),
        (RosterSyncScope.COHORT, True, True, True),
        (RosterSyncScope.COHORT, False, True, False),
    ],
)
def test_roster_sync_scope_requires_matching_targets(
    scope: RosterSyncScope, bootcamp: bool, cohort: bool, valid: bool
) -> None:
    def build() -> RosterSyncRun:
        return RosterSyncRun(
            trigger=RosterSyncTrigger.MANUAL,
            scope_type=scope,
            started_at=NOW,
            bootcamp_id=new_id() if bootcamp else None,
            cohort_id=new_id() if cohort else None,
        )

    if valid:
        build()
    else:
        with pytest.raises(BusinessRuleViolation):
            build()


def test_roster_sync_run_finishes_once() -> None:
    run = RosterSyncRun(
        trigger=RosterSyncTrigger.SCHEDULED, scope_type=RosterSyncScope.ALL, started_at=NOW
    )
    run.succeed(now=NOW, fetched=10, upserted=3, removed=1, unmapped=2)
    assert run.status is RosterSyncStatus.SUCCEEDED
    assert (run.fetched_count, run.upserted_count, run.removed_count, run.unmapped_count) == (
        10,
        3,
        1,
        2,
    )
    with pytest.raises(BusinessRuleViolation) as exc:
        run.fail(now=NOW, error_message="x")
    assert exc.value.code == "roster_sync_not_running"

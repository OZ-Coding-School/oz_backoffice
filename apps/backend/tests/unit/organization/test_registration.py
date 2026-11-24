import uuid
from datetime import UTC, datetime

import pytest

from app.contexts.organization.domain.enums import (
    AssignmentScope,
    EmployeeRegistrationStatus,
    EmploymentType,
)
from app.contexts.organization.domain.registration import (
    MAX_ASSIGNMENTS,
    EmployeeRegistration,
    RequestedAssignment,
    check_assignment_scope,
    check_employee_assignments,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def make_registration(**overrides: object) -> EmployeeRegistration:
    values: dict[str, object] = {
        "user_id": new_id(),
        "department_id": new_id(),
        "position_id": new_id(),
        "employment_type": EmploymentType.REGULAR,
    }
    values.update(overrides)
    return EmployeeRegistration(**values)  # type: ignore[arg-type]


def test_assignment_targets_exactly_one_scope() -> None:
    RequestedAssignment(bootcamp_id=new_id())
    RequestedAssignment(cohort_id=new_id())
    with pytest.raises(BusinessRuleViolation):
        RequestedAssignment()
    with pytest.raises(BusinessRuleViolation):
        RequestedAssignment(bootcamp_id=new_id(), cohort_id=new_id())


def test_registration_rejects_duplicate_and_too_many_assignments() -> None:
    cohort_id = new_id()
    same = RequestedAssignment(cohort_id=cohort_id)
    with pytest.raises(BusinessRuleViolation) as exc:
        make_registration(assignments=[same, same])
    assert exc.value.code == "duplicate_staff_assignment"

    too_many = [RequestedAssignment(cohort_id=new_id()) for _ in range(MAX_ASSIGNMENTS + 1)]
    with pytest.raises(BusinessRuleViolation):
        make_registration(assignments=too_many)


def test_registration_without_assignment_is_allowed() -> None:
    registration = make_registration()
    assert registration.is_pending
    assert registration.assignments == []


def test_only_pending_registration_can_be_updated() -> None:
    registration = make_registration()
    new_department = new_id()
    assignment = RequestedAssignment(bootcamp_id=new_id())
    new_team = new_id()
    registration.update(
        department_id=new_department,
        team_id=new_team,
        position_id=registration.position_id,
        employment_type=EmploymentType.CONTRACT,
        assignments=[assignment],
    )
    assert (registration.department_id, registration.team_id, registration.employment_type) == (
        new_department,
        new_team,
        EmploymentType.CONTRACT,
    )
    assert registration.assignments == [assignment]

    reviewed = make_registration(
        status=EmployeeRegistrationStatus.REJECTED,
        reviewed_at=datetime(2026, 11, 5, tzinfo=UTC),
        reject_reason="부서 확인 필요",
    )
    with pytest.raises(BusinessRuleViolation) as exc:
        reviewed.update(
            department_id=new_id(),
            team_id=None,
            position_id=new_id(),
            employment_type=EmploymentType.REGULAR,
            assignments=[],
        )
    assert exc.value.code == "registration_not_pending"


def test_status_and_reviewed_at_must_agree() -> None:
    with pytest.raises(BusinessRuleViolation):
        make_registration(status=EmployeeRegistrationStatus.APPROVED)
    with pytest.raises(BusinessRuleViolation):
        make_registration(reviewed_at=datetime(2026, 11, 5, tzinfo=UTC))


NOW = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


def test_approve_applies_adjusted_values() -> None:
    registration = make_registration(assignments=[RequestedAssignment(cohort_id=new_id())])
    department_id, position_id = new_id(), new_id()
    adjusted = [RequestedAssignment(bootcamp_id=new_id())]

    registration.approve(
        now=NOW,
        department_id=department_id,
        team_id=None,
        position_id=position_id,
        employment_type=EmploymentType.CONTRACT,
        assignments=adjusted,
    )

    assert registration.status is EmployeeRegistrationStatus.APPROVED
    assert registration.reviewed_at == NOW
    assert (registration.department_id, registration.position_id) == (department_id, position_id)
    assert registration.assignments == adjusted


def test_reject_requires_reason_and_pending() -> None:
    registration = make_registration()
    for reason in ("", "   ", "가" * 301):
        with pytest.raises(BusinessRuleViolation) as exc:
            registration.reject(now=NOW, reason=reason)
        assert exc.value.code == "invalid_reject_reason"

    registration.reject(now=NOW, reason="  담당 기수를 확인해 주세요 ")
    assert registration.status is EmployeeRegistrationStatus.REJECTED
    assert registration.reject_reason == "담당 기수를 확인해 주세요"

    with pytest.raises(BusinessRuleViolation) as exc:
        registration.reject(now=NOW, reason="다시")
    assert exc.value.code == "registration_not_pending"
    with pytest.raises(BusinessRuleViolation):
        registration.approve(
            now=NOW,
            department_id=new_id(),
            team_id=None,
            position_id=new_id(),
            employment_type=EmploymentType.REGULAR,
            assignments=[],
        )


class TestAssignmentScope:
    """직위 담당 방식 규칙 (A62, 신청할 때만 검사)."""

    team_bootcamp = new_id()
    other_bootcamp = new_id()
    team_cohort = new_id()
    other_cohort = new_id()

    def check(self, scope: AssignmentScope | None, *assignments: RequestedAssignment) -> None:
        check_assignment_scope(
            scope,
            list(assignments),
            team_bootcamp_ids={self.team_bootcamp},
            cohort_bootcamps={
                self.team_cohort: self.team_bootcamp,
                self.other_cohort: self.other_bootcamp,
            },
        )

    def manager(self, bootcamp_id: uuid.UUID) -> RequestedAssignment:
        return RequestedAssignment(bootcamp_id=bootcamp_id)

    def assistant(self, cohort_id: uuid.UUID) -> RequestedAssignment:
        return RequestedAssignment(cohort_id=cohort_id)

    def test_no_assignment_is_always_allowed(self) -> None:
        for scope in (None, AssignmentScope.COURSE, AssignmentScope.COHORT):
            self.check(scope)

    def test_course_scope_takes_team_courses_as_manager(self) -> None:
        self.check(AssignmentScope.COURSE, self.manager(self.team_bootcamp))
        for wrong in (
            self.manager(self.other_bootcamp),
            self.assistant(self.team_cohort),
        ):
            with pytest.raises(BusinessRuleViolation) as exc:
                self.check(AssignmentScope.COURSE, wrong)
            assert exc.value.code == "invalid_staff_assignment"

    def test_cohort_scope_takes_one_team_cohort_as_assistant(self) -> None:
        self.check(AssignmentScope.COHORT, self.assistant(self.team_cohort))
        for wrong in (
            (self.assistant(self.other_cohort),),
            (self.manager(self.team_bootcamp),),
            (self.assistant(self.team_cohort), self.assistant(self.other_cohort)),
        ):
            with pytest.raises(BusinessRuleViolation) as exc:
                self.check(AssignmentScope.COHORT, *wrong)
            assert exc.value.code == "invalid_staff_assignment"

    def test_cohort_with_assistant_cannot_be_taken(self) -> None:
        with pytest.raises(BusinessRuleViolation) as exc:
            check_assignment_scope(
                AssignmentScope.COHORT,
                [self.assistant(self.team_cohort)],
                team_bootcamp_ids={self.team_bootcamp},
                cohort_bootcamps={self.team_cohort: self.team_bootcamp},
                staffed_cohort_ids={self.team_cohort},
            )
        assert exc.value.code == "invalid_staff_assignment"

    def test_position_without_scope_cannot_take_assignments(self) -> None:
        with pytest.raises(BusinessRuleViolation) as exc:
            self.check(None, self.manager(self.team_bootcamp))
        assert exc.value.code == "invalid_staff_assignment"


class TestEmployeeAssignments:
    """직원 수정의 담당 지정 (A89)."""

    def test_rules(self) -> None:
        b1, b2, c1, c2 = new_id(), new_id(), new_id(), new_id()

        def check(scope: AssignmentScope | None, bs: list[uuid.UUID], cs: list[uuid.UUID]) -> None:
            check_employee_assignments(scope, bootcamp_ids=bs, cohort_ids=cs, taken_cohort_ids={c2})

        check(None, [], [])
        check(AssignmentScope.COURSE, [b1, b2], [])
        check(AssignmentScope.COHORT, [], [c1])
        check(AssignmentScope.COHORT, [], [])
        for scope, bs, cs, code in (
            (None, [b1], [], "invalid_staff_assignment"),
            (AssignmentScope.COURSE, [b1], [c1], "invalid_staff_assignment"),
            (AssignmentScope.COURSE, [b1, b1], [], "duplicate_staff_assignment"),
            (AssignmentScope.COHORT, [b1], [], "invalid_staff_assignment"),
            (AssignmentScope.COHORT, [], [c1, c2], "invalid_staff_assignment"),
            (AssignmentScope.COHORT, [], [c2], "invalid_staff_assignment"),  # 이미 담당 있음
        ):
            with pytest.raises(BusinessRuleViolation) as exc:
                check(scope, bs, cs)
            assert exc.value.code == code
        with pytest.raises(BusinessRuleViolation):
            check(AssignmentScope.COURSE, [new_id() for _ in range(MAX_ASSIGNMENTS + 1)], [])

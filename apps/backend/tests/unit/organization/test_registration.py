import uuid
from datetime import UTC, datetime

import pytest

from app.contexts.organization.domain.enums import (
    AssignmentScope,
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import (
    MAX_ASSIGNMENTS,
    EmployeeRegistration,
    RequestedAssignment,
    check_assignment_scope,
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
    RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=new_id())
    RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=new_id())
    with pytest.raises(BusinessRuleViolation):
        RequestedAssignment(role=StaffRole.MANAGER)
    with pytest.raises(BusinessRuleViolation):
        RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=new_id(), cohort_id=new_id())


def test_registration_rejects_duplicate_and_too_many_assignments() -> None:
    cohort_id = new_id()
    same = RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort_id)
    with pytest.raises(BusinessRuleViolation) as exc:
        make_registration(assignments=[same, same])
    assert exc.value.code == "duplicate_staff_assignment"
    # 같은 기수라도 역할이 다르면 허용한다
    make_registration(
        assignments=[same, RequestedAssignment(role=StaffRole.MANAGER, cohort_id=cohort_id)]
    )

    too_many = [
        RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=new_id())
        for _ in range(MAX_ASSIGNMENTS + 1)
    ]
    with pytest.raises(BusinessRuleViolation):
        make_registration(assignments=too_many)


def test_registration_without_assignment_is_allowed() -> None:
    registration = make_registration()
    assert registration.is_pending
    assert registration.assignments == []


def test_only_pending_registration_can_be_updated() -> None:
    registration = make_registration()
    new_department = new_id()
    assignment = RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=new_id())
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
    registration = make_registration(
        assignments=[RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=new_id())]
    )
    department_id, position_id = new_id(), new_id()
    adjusted = [RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=new_id())]

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
        return RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=bootcamp_id)

    def assistant(self, cohort_id: uuid.UUID) -> RequestedAssignment:
        return RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort_id)

    def test_no_assignment_is_always_allowed(self) -> None:
        for scope in (None, AssignmentScope.COURSE, AssignmentScope.COHORT):
            self.check(scope)

    def test_course_scope_takes_team_courses_as_manager(self) -> None:
        self.check(AssignmentScope.COURSE, self.manager(self.team_bootcamp))
        for wrong in (
            self.manager(self.other_bootcamp),
            self.assistant(self.team_cohort),
            RequestedAssignment(role=StaffRole.ASSISTANT, bootcamp_id=self.team_bootcamp),
        ):
            with pytest.raises(BusinessRuleViolation) as exc:
                self.check(AssignmentScope.COURSE, wrong)
            assert exc.value.code == "invalid_staff_assignment"

    def test_cohort_scope_takes_one_team_cohort_as_assistant(self) -> None:
        self.check(AssignmentScope.COHORT, self.assistant(self.team_cohort))
        for wrong in (
            (self.assistant(self.other_cohort),),
            (self.manager(self.team_bootcamp),),
            (self.assistant(self.team_cohort), self.assistant(self.team_cohort)),
        ):
            with pytest.raises(BusinessRuleViolation) as exc:
                self.check(AssignmentScope.COHORT, *wrong)
            assert exc.value.code == "invalid_staff_assignment"

    def test_position_without_scope_cannot_take_assignments(self) -> None:
        with pytest.raises(BusinessRuleViolation) as exc:
            self.check(None, self.manager(self.team_bootcamp))
        assert exc.value.code == "invalid_staff_assignment"

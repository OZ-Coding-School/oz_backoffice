from datetime import UTC, datetime

import pytest

from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import (
    MAX_ASSIGNMENTS,
    EmployeeRegistration,
    RequestedAssignment,
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
    registration.update(
        department_id=new_department,
        position_id=registration.position_id,
        employment_type=EmploymentType.CONTRACT,
        assignments=[assignment],
    )
    assert (registration.department_id, registration.employment_type) == (
        new_department,
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

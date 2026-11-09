import pytest

from app.contexts.organization.domain.entities import Department, Employee, EmployeePosition
from app.contexts.organization.domain.enums import EmploymentType
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def test_department_validates_and_trims() -> None:
    department = Department(name=" 교육 1팀 ", description=" 부트캠프 운영 ")
    assert (department.name, department.description) == ("교육 1팀", "부트캠프 운영")
    with pytest.raises(BusinessRuleViolation):
        Department(name="가" * 21, description="설명")
    with pytest.raises(BusinessRuleViolation):
        Department(name="팀", description="  ")


def test_department_cannot_be_its_own_parent() -> None:
    department = Department(name="교육팀", description="설명")
    with pytest.raises(BusinessRuleViolation):
        department.move_under(department.id)
    parent_id = new_id()
    department.move_under(parent_id)
    assert department.parent_id == parent_id
    with pytest.raises(BusinessRuleViolation):
        Department(id=parent_id, name="팀", description="설명", parent_id=parent_id)


def test_position_priority_must_be_non_negative() -> None:
    assert EmployeePosition(name=" 매니저 ", priority=3).name == "매니저"
    with pytest.raises(BusinessRuleViolation):
        EmployeePosition(name="매니저", priority=-1)


def test_employee_transfer() -> None:
    employee = Employee(
        user_id=new_id(),
        department_id=new_id(),
        position_id=new_id(),
        employment_type=EmploymentType.REGULAR,
    )
    department_id, position_id = new_id(), new_id()
    employee.transfer(department_id=department_id, position_id=position_id)
    assert (employee.department_id, employee.position_id) == (department_id, position_id)


def test_department_and_position_update_validate() -> None:
    department = Department(name="교육팀", description="설명")
    department.update(name=" 교육 1팀 ", description=" 운영 ", rules=None)
    assert (department.name, department.description) == ("교육 1팀", "운영")
    with pytest.raises(BusinessRuleViolation):
        department.update(name="", description="설명", rules=None)

    position = EmployeePosition(name="매니저", priority=3)
    position.update(name=" 팀장 ", priority=1)
    assert (position.name, position.priority) == ("팀장", 1)
    with pytest.raises(BusinessRuleViolation):
        position.update(name="팀장", priority=-1)

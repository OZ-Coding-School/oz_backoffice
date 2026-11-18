import pytest

from app.contexts.organization.domain.entities import (
    Department,
    Employee,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope, EmploymentType
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


def test_team_validates_and_trims() -> None:
    department_id = new_id()
    team = Team(department_id=department_id, name=" 교육 1팀 ", description="  ")
    assert (team.name, team.description) == ("교육 1팀", None)
    with pytest.raises(BusinessRuleViolation) as exc:
        Team(department_id=department_id, name=" ")
    assert exc.value.code == "invalid_team"
    with pytest.raises(BusinessRuleViolation):
        Team(department_id=department_id, name="팀", description="가" * 501)

    moved_to = new_id()
    team.update(department_id=moved_to, name="교육 2팀", description=" 운영 ")
    assert (team.department_id, team.name, team.description) == (moved_to, "교육 2팀", "운영")
    with pytest.raises(BusinessRuleViolation):
        team.update(department_id=moved_to, name="가" * 21, description=None)


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
    department_id, team_id, position_id = new_id(), new_id(), new_id()
    employee.transfer(department_id=department_id, team_id=team_id, position_id=position_id)
    assert (employee.department_id, employee.team_id, employee.position_id) == (
        department_id,
        team_id,
        position_id,
    )
    employee.transfer(department_id=department_id, team_id=None, position_id=position_id)
    assert employee.team_id is None


def test_department_and_position_update_validate() -> None:
    department = Department(name="교육팀", description="설명")
    department.update(name=" 교육 1팀 ", description=" 운영 ", rules=None)
    assert (department.name, department.description) == ("교육 1팀", "운영")
    with pytest.raises(BusinessRuleViolation):
        department.update(name="", description="설명", rules=None)

    position = EmployeePosition(name="매니저", priority=3)
    assert EmployeePosition(name="직원", priority=9).assignment_scope is None
    position.update(name=" 팀장 ", priority=1, assignment_scope=AssignmentScope.COURSE)
    assert (position.name, position.priority, position.assignment_scope) == (
        "팀장",
        1,
        AssignmentScope.COURSE,
    )
    with pytest.raises(BusinessRuleViolation):
        position.update(name="팀장", priority=-1, assignment_scope=None)

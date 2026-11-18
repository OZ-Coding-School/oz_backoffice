import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.entities import (
    BootcampStaff,
    CohortStaff,
    Department,
    Employee,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope, EmploymentType, StaffRole
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseBootcampTeamRepository,
    TortoiseCohortStaffRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)
from app.shared.errors import ConflictError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.factories.organization import create_department, create_employee, create_team

pytestmark = pytest.mark.integration


async def _create_employee(department: Department | None = None) -> Employee:
    departments = TortoiseDepartmentRepository()
    if department is None:
        department = Department(name="교육 1팀", description="부트캠프 운영")
        await departments.add(department)
    position = EmployeePosition(name=f"매니저{department.id.hex[-6:]}", priority=3)
    await TortoiseEmployeePositionRepository().add(position)
    user = make_user(email=f"{department.id.hex[-12:]}@nextrunners.co.kr")
    await TortoiseUserRepository().add(user)
    employee = Employee(
        user_id=user.id,
        department_id=department.id,
        position_id=position.id,
        employment_type=EmploymentType.REGULAR,
    )
    await TortoiseEmployeeRepository().add(employee)
    return employee


async def test_department_names_are_unique() -> None:
    departments = TortoiseDepartmentRepository()
    await departments.add(Department(name="경영지원", description="부서"))
    found = await departments.get_by_name(" 경영지원 ")
    assert found is not None
    assert await departments.get_by_name("없는 부서") is None
    with pytest.raises(IntegrityError):
        await departments.add(Department(name="경영지원", description="중복"))


async def test_team_unique_per_department_and_restricts_department_delete() -> None:
    teams = TortoiseTeamRepository()
    first, second = await create_department(), await create_department()
    team = Team(department_id=first.id, name="교육 1팀", description="운영")
    await teams.add(team)
    await teams.add(Team(department_id=second.id, name="교육 1팀"))  # 다른 부서면 허용
    found = await teams.find_by_department_and_name(first.id, " 교육 1팀 ")
    assert found is not None
    assert (found.id, found.description) == (team.id, "운영")
    assert [t.name for t in await teams.list_all()] == ["교육 1팀", "교육 1팀"]
    with pytest.raises(IntegrityError):
        await teams.add(Team(department_id=first.id, name="교육 1팀"))
    with pytest.raises(ConflictError) as exc:
        await TortoiseDepartmentRepository().delete(first.id)  # 팀이 참조 중
    assert exc.value.code == "in_use"


async def test_bootcamp_has_one_team() -> None:
    links = TortoiseBootcampTeamRepository()
    cohort = await create_cohort()
    first, second = await create_team(), await create_team()

    await links.assign(cohort.bootcamp_id, first.id)
    assert await links.list_bootcamp_ids(first.id) == {cohort.bootcamp_id}
    with pytest.raises(ConflictError):
        await TortoiseTeamRepository().delete(first.id)  # 담당 과정이 참조 중

    await links.assign(cohort.bootcamp_id, second.id)  # 담당 팀 변경
    link = await links.get(cohort.bootcamp_id)
    assert link is not None
    assert link.team_id == second.id
    assert [x.bootcamp_id for x in await links.list_all()] == [cohort.bootcamp_id]
    assert await links.list_bootcamp_ids(first.id) == set()

    with pytest.raises(IntegrityError):  # 과정당 한 팀
        await connections.get("default").execute_query(
            "INSERT INTO team_bootcamps (id, team_id, bootcamp_id, created_at) "
            "VALUES ($1, $2, $3, now())",
            [new_id(), first.id, cohort.bootcamp_id],
        )

    await links.assign(cohort.bootcamp_id, None)
    assert await links.get(cohort.bootcamp_id) is None
    await TortoiseTeamRepository().delete(first.id)


async def test_position_assignment_scope_round_trip_and_check() -> None:
    positions = TortoiseEmployeePositionRepository()
    position = EmployeePosition(name="조교", priority=4, assignment_scope=AssignmentScope.COHORT)
    await positions.add(position)
    loaded = await positions.get(position.id)
    assert loaded is not None
    assert loaded.assignment_scope is AssignmentScope.COHORT
    with pytest.raises(IntegrityError):
        await connections.get("default").execute_query(
            "UPDATE employee_positions SET assignment_scope = 'TEAM' WHERE id = $1",
            [position.id],
        )


async def test_employee_team_round_trip() -> None:
    employee = await create_employee()
    team = await create_team(employee.department_id)
    employee.transfer(
        department_id=employee.department_id, team_id=team.id, position_id=employee.position_id
    )
    await TortoiseEmployeeRepository().save(employee)
    loaded = await TortoiseEmployeeRepository().get(employee.id)
    assert loaded is not None
    assert loaded.team_id == team.id


async def test_employee_is_unique_per_user_and_found_by_user() -> None:
    employee = await _create_employee()
    employees = TortoiseEmployeeRepository()
    assert await employees.get_by_user(employee.user_id) == employee
    duplicate = Employee(
        user_id=employee.user_id,
        department_id=employee.department_id,
        position_id=employee.position_id,
        employment_type=EmploymentType.CONTRACT,
    )
    with pytest.raises(IntegrityError):
        await employees.add(duplicate)


async def test_staff_assignments() -> None:
    employee = await _create_employee()
    cohort = await create_cohort()
    cohort_staffs = TortoiseCohortStaffRepository()
    manager = CohortStaff(employee_id=employee.id, cohort_id=cohort.id, role=StaffRole.MANAGER)
    await cohort_staffs.add(manager)
    assert manager.created_at is not None
    # 같은 직원이 같은 기수에서 다른 역할을 맡는 것은 허용, 같은 역할 중복은 거부
    await cohort_staffs.add(
        CohortStaff(employee_id=employee.id, cohort_id=cohort.id, role=StaffRole.ASSISTANT)
    )
    with pytest.raises(IntegrityError):
        await cohort_staffs.add(
            CohortStaff(employee_id=employee.id, cohort_id=cohort.id, role=StaffRole.MANAGER)
        )
    assert {s.role for s in await cohort_staffs.list_by_cohort(cohort.id)} == {
        StaffRole.MANAGER,
        StaffRole.ASSISTANT,
    }
    await cohort_staffs.remove(manager.id)
    assert [s.role for s in await cohort_staffs.list_by_employee(employee.id)] == [
        StaffRole.ASSISTANT
    ]

    bootcamp_staffs = TortoiseBootcampStaffRepository()
    await bootcamp_staffs.add(
        BootcampStaff(
            employee_id=employee.id, bootcamp_id=cohort.bootcamp_id, role=StaffRole.MANAGER
        )
    )
    assert len(await bootcamp_staffs.list_by_bootcamp(cohort.bootcamp_id)) == 1


@pytest.mark.parametrize(
    ("sql", "constraint"),
    [
        ("UPDATE employees SET employment_type = 'UNKNOWN'", "check_employees_employment_type"),
        (
            "UPDATE employee_positions SET assignment_scope = 'TEAM'",
            "check_employee_positions_assignment_scope",
        ),
    ],
)
async def test_db_check_constraints(sql: str, constraint: str) -> None:
    await _create_employee()
    with pytest.raises(IntegrityError, match=constraint):
        await connections.get("default").execute_query(sql)


async def test_list_employees_by_ids() -> None:
    first, second = await create_employee(), await create_employee()
    found = await TortoiseEmployeeRepository().list_by_ids([first.id, second.id, new_id()])
    assert {e.id for e in found} == {first.id, second.id}
    assert await TortoiseEmployeeRepository().list_by_ids([]) == []


async def test_delete_in_use_is_conflict_and_lookups() -> None:
    departments = TortoiseDepartmentRepository()
    parent = Department(name="본부", description="설명")
    await departments.add(parent)
    team = await create_team(parent.id)

    with pytest.raises(ConflictError) as exc:
        await departments.delete(parent.id)  # 팀이 참조 중
    assert exc.value.code == "in_use"
    await TortoiseTeamRepository().delete(team.id)
    await departments.delete(parent.id)
    assert await departments.get(parent.id) is None

    employee = await create_employee()
    positions = TortoiseEmployeePositionRepository()
    position = await positions.get(employee.position_id)
    assert position is not None
    assert await positions.get_by_name(position.name) is not None
    with pytest.raises(ConflictError):
        await positions.delete(employee.position_id)


async def test_employee_page_by_department() -> None:
    first, second = await create_employee(), await create_employee()
    page, total = await TortoiseEmployeeRepository().list_page(
        department_id=None, limit=1, offset=1
    )
    assert (total, [e.id for e in page]) == (2, [second.id])
    only, count_one = await TortoiseEmployeeRepository().list_page(
        department_id=first.department_id, limit=10, offset=0
    )
    assert (count_one, [e.id for e in only]) == (1, [first.id])

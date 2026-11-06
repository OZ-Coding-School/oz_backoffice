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
)
from app.contexts.organization.domain.enums import EmploymentType, StaffRole
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
)
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.factories.organization import create_employee

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


async def test_department_tree_and_unique_name_per_parent() -> None:
    departments = TortoiseDepartmentRepository()
    root = Department(name="교육본부", description="교육 총괄")
    await departments.add(root)
    child = Department(name="교육 1팀", description="부트캠프 운영", parent_id=root.id)
    await departments.add(child)
    # 다른 상위 부서 아래에서는 같은 이름 허용
    await departments.add(Department(name="교육 1팀", description="다른 본부", parent_id=None))
    assert {d.name for d in await departments.list_all()} == {"교육본부", "교육 1팀"}

    with pytest.raises(IntegrityError):
        await departments.add(Department(name="교육 1팀", description="중복", parent_id=root.id))


async def test_top_level_department_names_are_unique_nulls_not_distinct() -> None:
    departments = TortoiseDepartmentRepository()
    await departments.add(Department(name="경영지원", description="최상위"))
    with pytest.raises(IntegrityError):
        await departments.add(Department(name="경영지원", description="최상위 중복"))


async def test_department_parent_fk_restricts_delete() -> None:
    departments = TortoiseDepartmentRepository()
    root = Department(name="교육본부", description="교육 총괄")
    await departments.add(root)
    await departments.add(Department(name="교육 1팀", description="운영", parent_id=root.id))
    with pytest.raises(IntegrityError):
        await connections.get("default").execute_query(
            "DELETE FROM departments WHERE id = $1", [root.id]
        )


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
        ("UPDATE departments SET parent_id = id", "check_departments_parent_not_self"),
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

"""권한 테스트 데이터 (decisions A87): 최고 관리자 필드, 직위 권한·데이터 범위, 담당 배정.

`give_role`은 예전 역할 부여를 흉내 낸다(직위 = 역할). 테스트에서 '운영 매니저를 과정 X에'처럼
쓰던 셋업을 그대로 옮기기 위해서다.
"""

import uuid

from app.contexts.access.domain.catalog import DEV_POSITION_PERMISSIONS
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.entities import BootcampStaff, CohortStaff, Employee
from app.contexts.organization.domain.enums import DataScope, EmploymentType, StaffRole
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
)
from tests.factories.organization import create_department, create_position

SUPER_ADMIN = "SUPER_ADMIN"
TEAM_LEAD = "팀리드"
MANAGER = "운영 매니저"
ASSISTANT = "조교"


async def make_super_admin(user_id: uuid.UUID) -> None:
    repo = TortoiseUserRepository()
    user = await repo.get(user_id)
    assert user is not None
    user.set_super_admin(True)
    await repo.save(user)


async def give_permissions(
    user_id: uuid.UUID,
    permissions: frozenset[str] | set[str],
    *,
    all_data: bool = False,
    bootcamp_ids: tuple[uuid.UUID, ...] = (),
    cohort_ids: tuple[uuid.UUID, ...] = (),
) -> Employee:
    """그 권한을 가진 새 직위로 직원을 만들거나 바꾸고, 담당을 더한다."""
    position = await create_position()
    if all_data:
        position.update(
            name=position.name,
            priority=position.priority,
            assignment_scope=position.assignment_scope,
            data_scope=DataScope.ALL,
        )
        await TortoiseEmployeePositionRepository().save(position)
    await TortoiseEmployeePositionRepository().replace_permissions(
        position.id, frozenset(permissions)
    )
    employees = TortoiseEmployeeRepository()
    employee = await employees.get_by_user(user_id)
    if employee is None:
        employee = Employee(
            user_id=user_id,
            department_id=(await create_department()).id,
            position_id=position.id,
            employment_type=EmploymentType.REGULAR,
        )
        await employees.add(employee)
    else:
        employee.transfer(
            department_id=employee.department_id, team_id=employee.team_id, position_id=position.id
        )
        await employees.save(employee)
    await assign(employee, bootcamp_ids=bootcamp_ids, cohort_ids=cohort_ids)
    return employee


async def assign(
    employee: Employee,
    *,
    bootcamp_ids: tuple[uuid.UUID, ...] = (),
    cohort_ids: tuple[uuid.UUID, ...] = (),
) -> None:
    for bootcamp_id in bootcamp_ids:
        await TortoiseBootcampStaffRepository().add(
            BootcampStaff(employee_id=employee.id, bootcamp_id=bootcamp_id, role=StaffRole.MANAGER)
        )
    for cohort_id in cohort_ids:
        await TortoiseCohortStaffRepository().add(
            CohortStaff(employee_id=employee.id, cohort_id=cohort_id, role=StaffRole.ASSISTANT)
        )


async def give_role(
    user_id: uuid.UUID,
    role: str,
    *,
    bootcamp_id: uuid.UUID | None = None,
    cohort_id: uuid.UUID | None = None,
) -> None:
    """예전 역할 셋업을 직위로 옮긴다: 최고 관리자 → 회원 필드, 팀리드 → 전체 데이터 직위,
    운영 매니저·조교 → 담당만 직위 + 그 과정·기수 담당."""
    if role == SUPER_ADMIN:
        await make_super_admin(user_id)
        return
    existing = await TortoiseEmployeeRepository().get_by_user(user_id)
    bootcamps = (bootcamp_id,) if bootcamp_id else ()
    cohorts = (cohort_id,) if cohort_id else ()
    if existing is not None and role != TEAM_LEAD:
        await assign(existing, bootcamp_ids=bootcamps, cohort_ids=cohorts)  # 담당만 더한다
        return
    await give_permissions(
        user_id,
        DEV_POSITION_PERMISSIONS[role],
        all_data=role == TEAM_LEAD,
        bootcamp_ids=bootcamps,
        cohort_ids=cohorts,
    )

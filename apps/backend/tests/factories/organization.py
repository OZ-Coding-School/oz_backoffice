"""organization 테스트 데이터 빌더."""

import uuid
from itertools import count

from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.entities import (
    Department,
    Employee,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope, EmploymentType
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampTeamRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)
from app.shared.ids import new_id
from tests.factories.identity import make_user

_seq = count(1)


async def create_department(name: str | None = None) -> Department:
    department = Department(name=name or f"부서{next(_seq)}", description="테스트 부서")
    await TortoiseDepartmentRepository().add(department)
    return department


async def create_team(
    department_id: uuid.UUID | None = None,
    name: str | None = None,
    *,
    bootcamp_ids: tuple[uuid.UUID, ...] = (),
) -> Team:
    """팀(부서가 없으면 부서까지)을 만들고 담당 과정을 연결한다."""
    team = Team(
        department_id=department_id or (await create_department()).id,
        name=name or f"팀{next(_seq)}",
    )
    await TortoiseTeamRepository().add(team)
    for bootcamp_id in bootcamp_ids:
        await TortoiseBootcampTeamRepository().assign(bootcamp_id, team.id)
    return team


async def create_position(
    name: str | None = None,
    priority: int = 5,
    assignment_scope: AssignmentScope | None = None,
) -> EmployeePosition:
    position = EmployeePosition(
        name=name or f"직위{next(_seq)}", priority=priority, assignment_scope=assignment_scope
    )
    await TortoiseEmployeePositionRepository().add(position)
    return position


async def create_employee(
    user: User | None = None, *, employment_type: EmploymentType = EmploymentType.REGULAR
) -> Employee:
    """부서·직위(와 회원이 없으면 회원)까지 만들어 직원을 저장한다."""
    if user is None:
        user = make_user(email=f"emp{new_id().hex[-12:]}@nextrunners.co.kr")
        await TortoiseUserRepository().add(user)
    employee = Employee(
        user_id=user.id,
        department_id=(await create_department()).id,
        position_id=(await create_position()).id,
        employment_type=employment_type,
    )
    await TortoiseEmployeeRepository().add(employee)
    return employee

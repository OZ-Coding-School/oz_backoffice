"""부서·팀·직위를 지우거나 바꿀 때 영향받는 대상 (A93).

확인 창이 '직원 N명' 대신 실제 대상을 목록으로 보여 주도록, 그 부서·팀·직위를 쓰는
직원·운영진 가입 신청과 딸린 팀·담당 과정을 모아 준다. 읽기만 한다.
"""

import uuid
from dataclasses import dataclass, field

from app.contexts.organization.domain.entities import Employee, Team
from app.contexts.organization.domain.registration import EmployeeRegistration
from app.contexts.organization.domain.repositories import (
    BootcampTeamRepository,
    DepartmentRepository,
    EmployeePositionRepository,
    EmployeeRegistrationRepository,
    EmployeeRepository,
    TeamRepository,
)
from app.shared.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class OrgImpact:
    employees: list[Employee]
    registrations: list[EmployeeRegistration]
    teams: list[Team] = field(default_factory=list)
    bootcamp_ids: list[uuid.UUID] = field(default_factory=list)


class OrgImpactQueries:
    def __init__(
        self,
        *,
        departments: DepartmentRepository,
        teams: TeamRepository,
        bootcamp_teams: BootcampTeamRepository,
        positions: EmployeePositionRepository,
        employees: EmployeeRepository,
        registrations: EmployeeRegistrationRepository,
    ) -> None:
        self._departments = departments
        self._teams = teams
        self._bootcamp_teams = bootcamp_teams
        self._positions = positions
        self._employees = employees
        self._registrations = registrations

    async def of_department(self, department_id: uuid.UUID) -> OrgImpact:
        """부서의 직원(팀 포함)·신청·팀."""
        if await self._departments.get(department_id) is None:
            raise NotFoundError("부서를 찾을 수 없습니다.", code="department_not_found")
        teams = [t for t in await self._teams.list_all() if t.department_id == department_id]
        return OrgImpact(
            employees=await self._employees.search(department_id=department_id),
            registrations=await self._registrations.list_referencing(department_id=department_id),
            teams=teams,
        )

    async def of_team(self, team_id: uuid.UUID) -> OrgImpact:
        """팀의 직원·신청·담당 과정."""
        if await self._teams.get(team_id) is None:
            raise NotFoundError("팀을 찾을 수 없습니다.", code="team_not_found")
        return OrgImpact(
            employees=await self._employees.search(team_id=team_id),
            registrations=await self._registrations.list_referencing(team_id=team_id),
            bootcamp_ids=sorted(await self._bootcamp_teams.list_bootcamp_ids(team_id), key=str),
        )

    async def of_position(self, position_id: uuid.UUID) -> OrgImpact:
        """그 직위의 직원·신청."""
        if await self._positions.get(position_id) is None:
            raise NotFoundError("직위를 찾을 수 없습니다.", code="position_not_found")
        return OrgImpact(
            employees=await self._employees.search(position_id=position_id),
            registrations=await self._registrations.list_referencing(position_id=position_id),
        )

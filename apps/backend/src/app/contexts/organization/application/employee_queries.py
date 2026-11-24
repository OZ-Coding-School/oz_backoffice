"""organization 공개 조회 (다른 컨텍스트용).

app.main이 app.state.employee_queries에 연결한다(decisions B10).
"""

import uuid
from dataclasses import dataclass

from app.contexts.organization.domain.repositories import (
    DepartmentRepository,
    EmployeePositionRepository,
    EmployeeRepository,
    TeamRepository,
)


@dataclass(frozen=True, slots=True)
class EmployeeAffiliation:
    """회원의 직원 소속 이름 (역할 보유자 목록 등 표시용, A85)."""

    department_name: str | None
    team_name: str | None
    position_name: str | None


class EmployeeQueries:
    def __init__(
        self,
        employees: EmployeeRepository,
        *,
        departments: DepartmentRepository | None = None,
        teams: TeamRepository | None = None,
        positions: EmployeePositionRepository | None = None,
    ) -> None:
        self._employees = employees
        self._departments = departments
        self._teams = teams
        self._positions = positions

    async def exists(self, employee_id: uuid.UUID) -> bool:
        return await self._employees.get(employee_id) is not None

    async def affiliations(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, EmployeeAffiliation]:
        """직원 정보가 있는 회원만 담는다. 부서·팀·직위는 수가 적어 한 번씩 모두 읽는다."""
        employees = await self._employees.list_by_users(user_ids)
        if not employees:
            return {}
        if self._departments is None or self._teams is None or self._positions is None:
            raise RuntimeError("소속 이름을 읽으려면 부서·팀·직위 저장소가 필요합니다.")
        departments = {d.id: d.name for d in await self._departments.list_all()}
        teams = {t.id: t.name for t in await self._teams.list_all()}
        positions = {p.id: p.name for p in await self._positions.list_all()}
        return {
            e.user_id: EmployeeAffiliation(
                department_name=departments.get(e.department_id),
                team_name=teams.get(e.team_id) if e.team_id else None,
                position_name=positions.get(e.position_id),
            )
            for e in employees
        }

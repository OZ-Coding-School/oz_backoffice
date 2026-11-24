"""organization 공개 조회 (다른 컨텍스트용).

app.main이 app.state.employee_queries에 연결한다(decisions B10).
"""

import uuid
from dataclasses import dataclass

from app.contexts.organization.domain.enums import DataScope
from app.contexts.organization.domain.repositories import (
    BootcampStaffRepository,
    CohortStaffRepository,
    EmployeePositionRepository,
    EmployeeRepository,
)


@dataclass(frozen=True, slots=True)
class EmployeeAccessView:
    """직원의 권한과 데이터 범위 (A87): 직위의 권한·데이터 범위 + 담당 배정."""

    position_id: uuid.UUID
    position_name: str
    permissions: frozenset[str]
    all_data: bool
    bootcamp_ids: frozenset[uuid.UUID]
    cohort_ids: frozenset[uuid.UUID]


class EmployeeQueries:
    def __init__(
        self,
        employees: EmployeeRepository,
        *,
        positions: EmployeePositionRepository | None = None,
        bootcamp_staffs: BootcampStaffRepository | None = None,
        cohort_staffs: CohortStaffRepository | None = None,
    ) -> None:
        self._employees = employees
        self._positions = positions
        self._bootcamp_staffs = bootcamp_staffs
        self._cohort_staffs = cohort_staffs

    async def exists(self, employee_id: uuid.UUID) -> bool:
        return await self._employees.get(employee_id) is not None

    async def access_of(self, user_id: uuid.UUID) -> EmployeeAccessView | None:
        """직원이 아니면 None (권한 없음)."""
        if self._positions is None or self._bootcamp_staffs is None or self._cohort_staffs is None:
            raise RuntimeError("권한을 읽으려면 직위·담당자 저장소가 필요합니다.")
        employee = await self._employees.get_by_user(user_id)
        if employee is None:
            return None
        position = await self._positions.get(employee.position_id)
        if position is None:
            return None
        return EmployeeAccessView(
            position_id=position.id,
            position_name=position.name,
            permissions=await self._positions.permissions_of(position.id),
            all_data=position.data_scope is DataScope.ALL,
            bootcamp_ids=frozenset(
                s.bootcamp_id for s in await self._bootcamp_staffs.list_by_employee(employee.id)
            ),
            cohort_ids=frozenset(
                s.cohort_id for s in await self._cohort_staffs.list_by_employee(employee.id)
            ),
        )

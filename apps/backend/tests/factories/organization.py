"""organization 테스트 데이터 빌더."""

from itertools import count

from app.contexts.organization.domain.entities import Department, EmployeePosition
from app.contexts.organization.infrastructure.repositories import (
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
)

_seq = count(1)


async def create_department(name: str | None = None) -> Department:
    department = Department(name=name or f"부서{next(_seq)}", description="테스트 부서")
    await TortoiseDepartmentRepository().add(department)
    return department


async def create_position(name: str | None = None, priority: int = 5) -> EmployeePosition:
    position = EmployeePosition(name=name or f"직위{next(_seq)}", priority=priority)
    await TortoiseEmployeePositionRepository().add(position)
    return position

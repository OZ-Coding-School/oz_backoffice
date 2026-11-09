"""조직 마스터 관리 (부서·직위·직원). 권한 org.manage (decisions D5: 부서는 조직도 용도).

- 부서: 같은 상위 안에서 이름 유일, 상위 변경 시 여러 단계 순환 금지, 참조 중이면 삭제 불가
- 직위: 이름 유일, 직원이 쓰는 직위는 삭제 불가
- 직원: 가입 승인(P3-2b)으로 만들어진다. 여기서는 조회와 부서·직위·고용 형태 이동만 한다
모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.organization.domain.entities import Department, Employee, EmployeePosition
from app.contexts.organization.domain.enums import EmploymentType
from app.contexts.organization.domain.repositories import (
    DepartmentRepository,
    EmployeePositionRepository,
    EmployeeRepository,
)
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError

_UNSET: Any = object()


def _snapshot(entity: object) -> dict[str, Any]:
    return {
        k: str(v) if isinstance(v, uuid.UUID) else v
        for k, v in vars(entity).items()
        if not k.startswith("_") and k != "id"
    }


@dataclass(frozen=True, slots=True)
class DepartmentChanges:
    """부서 수정 항목. 보내지 않은 항목은 _UNSET(그대로)."""

    name: str = _UNSET
    description: str = _UNSET
    rules: str | None = _UNSET
    parent_id: uuid.UUID | None = _UNSET


class OrganizationAdminService:
    def __init__(
        self,
        *,
        departments: DepartmentRepository,
        positions: EmployeePositionRepository,
        employees: EmployeeRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._departments = departments
        self._positions = positions
        self._employees = employees
        self._audit = audit
        self._uow = uow

    # ------------------------------------------------------------------ 부서
    async def list_departments(self) -> list[Department]:
        return await self._departments.list_all()

    async def create_department(
        self,
        *,
        name: str,
        description: str,
        parent_id: uuid.UUID | None,
        rules: str | None,
        actor_id: uuid.UUID,
    ) -> Department:
        department = Department(
            name=name, description=description, parent_id=parent_id, rules=rules
        )
        async with self._uow:
            if parent_id is not None:
                await self._get_department(parent_id, code="parent_department_not_found")
            await self._ensure_department_name_free(parent_id, department.name)
            await self._departments.add(department)
            await self._record(
                actor_id, "department.create", department, after=_snapshot(department)
            )
        return department

    async def update_department(
        self, department_id: uuid.UUID, changes: DepartmentChanges, *, actor_id: uuid.UUID
    ) -> Department:
        async with self._uow:
            department = await self._get_department(department_id)
            before = _snapshot(department)
            parent_id = department.parent_id if changes.parent_id is _UNSET else changes.parent_id
            if parent_id != department.parent_id:
                await self._ensure_no_cycle(department.id, parent_id)
                department.move_under(parent_id)
            department.update(
                name=department.name if changes.name is _UNSET else changes.name,
                description=department.description
                if changes.description is _UNSET
                else changes.description,
                rules=department.rules if changes.rules is _UNSET else changes.rules,
            )
            if (before["name"], before["parent_id"]) != (
                department.name,
                _str(department.parent_id),
            ):
                await self._ensure_department_name_free(
                    department.parent_id, department.name, exclude=department.id
                )
            await self._departments.save(department)
            await self._record(
                actor_id,
                "department.update",
                department,
                before=before,
                after=_snapshot(department),
            )
        return department

    async def delete_department(self, department_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            department = await self._get_department(department_id)
            await self._departments.delete(department_id)  # 하위 부서·직원·신청이 참조 중이면 409
            await self._record(
                actor_id, "department.delete", department, before=_snapshot(department)
            )

    # ------------------------------------------------------------------ 직위
    async def list_positions(self) -> list[EmployeePosition]:
        return await self._positions.list_all()

    async def create_position(
        self, *, name: str, priority: int, actor_id: uuid.UUID
    ) -> EmployeePosition:
        position = EmployeePosition(name=name, priority=priority)
        async with self._uow:
            await self._ensure_position_name_free(position.name)
            await self._positions.add(position)
            await self._record(actor_id, "position.create", position, after=_snapshot(position))
        return position

    async def update_position(
        self,
        position_id: uuid.UUID,
        *,
        name: str | None,
        priority: int | None,
        actor_id: uuid.UUID,
    ) -> EmployeePosition:
        async with self._uow:
            position = await self._get_position(position_id)
            before = _snapshot(position)
            position.update(
                name=position.name if name is None else name,
                priority=position.priority if priority is None else priority,
            )
            if position.name != before["name"]:
                await self._ensure_position_name_free(position.name)
            await self._positions.save(position)
            await self._record(
                actor_id, "position.update", position, before=before, after=_snapshot(position)
            )
        return position

    async def delete_position(self, position_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            position = await self._get_position(position_id)
            await self._positions.delete(position_id)  # 직원·신청이 쓰는 직위면 409
            await self._record(actor_id, "position.delete", position, before=_snapshot(position))

    # ------------------------------------------------------------------ 직원
    async def list_employees(
        self, *, department_id: uuid.UUID | None, limit: int, offset: int
    ) -> tuple[list[Employee], int]:
        return await self._employees.list_page(
            department_id=department_id, limit=limit, offset=offset
        )

    async def get_employee(self, employee_id: uuid.UUID) -> Employee:
        employee = await self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("직원을 찾을 수 없습니다.", code="employee_not_found")
        return employee

    async def update_employee(
        self,
        employee_id: uuid.UUID,
        *,
        department_id: uuid.UUID | None,
        position_id: uuid.UUID | None,
        employment_type: EmploymentType | None,
        actor_id: uuid.UUID,
    ) -> Employee:
        async with self._uow:
            employee = await self.get_employee(employee_id)
            before = _snapshot(employee)
            if department_id is not None:
                await self._get_department(department_id)
            if position_id is not None:
                await self._get_position(position_id)
            employee.transfer(
                department_id=department_id or employee.department_id,
                position_id=position_id or employee.position_id,
            )
            if employment_type is not None:
                employee.change_employment_type(employment_type)
            await self._employees.save(employee)
            await self._record(
                actor_id, "employee.update", employee, before=before, after=_snapshot(employee)
            )
        return employee

    # ------------------------------------------------------------------ 내부
    async def _get_department(
        self, department_id: uuid.UUID, *, code: str = "department_not_found"
    ) -> Department:
        department = await self._departments.get(department_id)
        if department is None:
            raise NotFoundError("부서를 찾을 수 없습니다.", code=code)
        return department

    async def _get_position(self, position_id: uuid.UUID) -> EmployeePosition:
        position = await self._positions.get(position_id)
        if position is None:
            raise NotFoundError("직위를 찾을 수 없습니다.", code="position_not_found")
        return position

    async def _ensure_department_name_free(
        self, parent_id: uuid.UUID | None, name: str, *, exclude: uuid.UUID | None = None
    ) -> None:
        existing = await self._departments.find_by_parent_and_name(parent_id, name)
        if existing is not None and existing.id != exclude:
            raise ConflictError(
                "같은 상위 부서에 같은 이름이 있습니다.", code="department_name_taken"
            )

    async def _ensure_position_name_free(self, name: str) -> None:
        if await self._positions.get_by_name(name) is not None:
            raise ConflictError("같은 이름의 직위가 있습니다.", code="position_name_taken")

    async def _ensure_no_cycle(self, department_id: uuid.UUID, parent_id: uuid.UUID | None) -> None:
        """새 상위 부서에서 위로 올라가며 자기 자신을 만나면 순환이다."""
        if parent_id is None:
            return
        parents = {d.id: d.parent_id for d in await self._departments.list_all()}
        if parent_id not in parents:
            raise NotFoundError("상위 부서를 찾을 수 없습니다.", code="parent_department_not_found")
        current: uuid.UUID | None = parent_id
        while current is not None:
            if current == department_id:
                raise BusinessRuleViolation(
                    "하위 부서를 상위 부서로 지정할 수 없습니다.", code="department_cycle"
                )
            current = parents.get(current)

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        entity: Department | EmployeePosition | Employee,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        target = {
            "department": "department",
            "position": "employee_position",
            "employee": "employee",
        }
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"organization.{action}",
            target_type=target[action.split(".", 1)[0]],
            target_id=entity.id,
            before=before,
            after=after,
        )


def _str(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None

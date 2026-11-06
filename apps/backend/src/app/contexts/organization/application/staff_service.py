"""과정·기수 담당자 배정·해제 (decisions D4).

담당자 행(bootcamp_staffs·cohort_staffs)은 화면 표시용이고 권한은 user_roles로 판정한다.
배정·해제할 때 같은 트랜잭션에서 대응하는 역할을 부여·회수해 둘을 맞춘다.
- 과정 담당: 매니저 → COHORT_MANAGER(BOOTCAMP), 조교 → COHORT_ASSISTANT(BOOTCAMP)
- 기수 담당: 매니저 → COHORT_MANAGER(COHORT), 조교 → COHORT_ASSISTANT(COHORT)
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.organization.application.registration_service import StaffTargetCatalog
from app.contexts.organization.application.staff_roles import StaffRoleSync, role_scope
from app.contexts.organization.domain.entities import BootcampStaff, CohortStaff
from app.contexts.organization.domain.enums import StaffRole
from app.contexts.organization.domain.repositories import (
    BootcampStaffRepository,
    CohortStaffRepository,
    EmployeeRepository,
)
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError, NotFoundError


class StaffTarget(StrEnum):
    BOOTCAMP = "BOOTCAMP"
    COHORT = "COHORT"


@dataclass(frozen=True, slots=True)
class StaffMember:
    """담당자 1명 (조회용). 회원 정보는 표시할 때 identity에서 붙인다."""

    id: uuid.UUID
    target: StaffTarget
    target_id: uuid.UUID
    employee_id: uuid.UUID
    user_id: uuid.UUID | None
    role: StaffRole
    created_at: datetime | None


Staff = BootcampStaff | CohortStaff


class StaffAssignmentService:
    def __init__(
        self,
        *,
        employees: EmployeeRepository,
        bootcamp_staffs: BootcampStaffRepository,
        cohort_staffs: CohortStaffRepository,
        catalog: StaffTargetCatalog,
        roles: StaffRoleSync,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._employees = employees
        self._bootcamp_staffs = bootcamp_staffs
        self._cohort_staffs = cohort_staffs
        self._catalog = catalog
        self._roles = roles
        self._audit = audit
        self._uow = uow

    async def list_members(
        self, target: StaffTarget, target_id: uuid.UUID
    ) -> Sequence[StaffMember]:
        staffs = await self._list_rows(target, target_id)
        employees = {
            e.id: e for e in await self._employees.list_by_ids([s.employee_id for s in staffs])
        }
        return [
            _member(
                target,
                target_id,
                s,
                employees[s.employee_id].user_id if s.employee_id in employees else None,
            )
            for s in staffs
        ]

    async def assign(
        self,
        target: StaffTarget,
        target_id: uuid.UUID,
        *,
        employee_id: uuid.UUID,
        role: StaffRole,
        actor_id: uuid.UUID,
    ) -> StaffMember:
        if target is StaffTarget.BOOTCAMP:
            await self._catalog.ensure_staffable(bootcamp_ids=[target_id], cohort_ids=[])
        else:
            await self._catalog.ensure_staffable(bootcamp_ids=[], cohort_ids=[target_id])
        async with self._uow:
            employee = await self._employees.get(employee_id)
            if employee is None:
                raise NotFoundError("직원을 찾을 수 없습니다.", code="employee_not_found")
            existing = await self._list_rows(target, target_id)
            if any(s.employee_id == employee_id and s.role is role for s in existing):
                raise ConflictError(
                    "이미 같은 역할로 배정된 담당자입니다.", code="staff_already_assigned"
                )
            staff: Staff
            if target is StaffTarget.BOOTCAMP:
                staff = BootcampStaff(employee_id=employee_id, bootcamp_id=target_id, role=role)
                await self._bootcamp_staffs.add(staff)
            else:
                staff = CohortStaff(employee_id=employee_id, cohort_id=target_id, role=role)
                await self._cohort_staffs.add(staff)
            await self._roles.grant(employee.user_id, *_role_scope(target, target_id, role))
            await self._audit.record(
                actor_user_id=actor_id,
                action="organization.staff.assign",
                target_type=target.value.lower(),
                target_id=target_id,
                after={"employee_id": str(employee_id), "role": role.value},
            )
        return _member(target, target_id, staff, employee.user_id)

    async def unassign(
        self, target: StaffTarget, target_id: uuid.UUID, staff_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        async with self._uow:
            staff = next(
                (s for s in await self._list_rows(target, target_id) if s.id == staff_id), None
            )
            if staff is None:
                raise NotFoundError("담당자를 찾을 수 없습니다.", code="staff_not_found")
            if target is StaffTarget.BOOTCAMP:
                await self._bootcamp_staffs.remove(staff_id)
            else:
                await self._cohort_staffs.remove(staff_id)
            employee = await self._employees.get(staff.employee_id)
            if employee is not None:
                await self._roles.revoke(
                    employee.user_id, *_role_scope(target, target_id, staff.role)
                )
            await self._audit.record(
                actor_user_id=actor_id,
                action="organization.staff.unassign",
                target_type=target.value.lower(),
                target_id=target_id,
                before={"employee_id": str(staff.employee_id), "role": staff.role.value},
            )

    async def _list_rows(self, target: StaffTarget, target_id: uuid.UUID) -> list[Staff]:
        if target is StaffTarget.BOOTCAMP:
            return list(await self._bootcamp_staffs.list_by_bootcamp(target_id))
        return list(await self._cohort_staffs.list_by_cohort(target_id))


def _role_scope(
    target: StaffTarget, target_id: uuid.UUID, role: StaffRole
) -> tuple[str, RoleScopeType, uuid.UUID]:
    if target is StaffTarget.BOOTCAMP:
        return role_scope(role, bootcamp_id=target_id)
    return role_scope(role, cohort_id=target_id)


def _member(
    target: StaffTarget, target_id: uuid.UUID, staff: Staff, user_id: uuid.UUID | None
) -> StaffMember:
    return StaffMember(
        id=staff.id,
        target=target,
        target_id=target_id,
        employee_id=staff.employee_id,
        user_id=user_id,
        role=staff.role,
        created_at=staff.created_at,
    )

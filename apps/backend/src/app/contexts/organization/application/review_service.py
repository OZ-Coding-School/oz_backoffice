"""운영진 가입 신청 검토(승인·반려) 유스케이스 (decisions A11·A12, D4).

승인은 한 트랜잭션에서 아래를 모두 처리한다.
1. 신청을 어드민이 조정한 항목으로 승인
2. 직원(`employees`) 생성 또는 부서·팀·직위·고용 형태 갱신
3. 담당자(`bootcamp_staffs`·`cohort_staffs`) 추가 (이미 있으면 건너뜀)
4. 담당에 맞는 역할(`user_roles`) 부여: 매니저 → COHORT_MANAGER, 조교 → COHORT_ASSISTANT
5. 회원 승인, 감사 로그
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.registration_service import (
    RegistrationChoiceValidator,
)
from app.contexts.organization.application.staff_roles import StaffRoleGranter, role_scope
from app.contexts.organization.domain.entities import BootcampStaff, CohortStaff, Employee
from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
)
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.domain.repositories import (
    BootcampStaffRepository,
    CohortStaffRepository,
    EmployeeRegistrationRepository,
    EmployeeRepository,
)
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError


class StaffUserApprover(Protocol):
    """identity `UserAdministration`이 구현."""

    async def approve(self, user_id: uuid.UUID) -> User: ...
    async def mark_rejected(self, user_id: uuid.UUID) -> User: ...


@dataclass(frozen=True, slots=True)
class RegistrationAdjustment:
    """승인할 때 어드민이 바꾸는 항목. 보내지 않은 항목은 신청한 값을 그대로 쓴다.

    팀은 None(부서 직속)으로 바꿀 수 있어 보내지 않음을 `team_changed`로 구분한다.
    조정은 자유이고 존재만 검사한다 (A62).
    """

    department_id: uuid.UUID | None = None
    team_changed: bool = False
    team_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    employment_type: EmploymentType | None = None
    assignments: list[RequestedAssignment] | None = None


class StaffRegistrationReviewService:
    def __init__(
        self,
        *,
        registrations: EmployeeRegistrationRepository,
        employees: EmployeeRepository,
        bootcamp_staffs: BootcampStaffRepository,
        cohort_staffs: CohortStaffRepository,
        validator: RegistrationChoiceValidator,
        users: StaffUserApprover,
        roles: StaffRoleGranter,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._registrations = registrations
        self._employees = employees
        self._bootcamp_staffs = bootcamp_staffs
        self._cohort_staffs = cohort_staffs
        self._validator = validator
        self._users = users
        self._roles = roles
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def list_by_status(
        self, status: EmployeeRegistrationStatus, *, limit: int, offset: int
    ) -> tuple[list[EmployeeRegistration], int]:
        return await self._registrations.list_by_status(status, limit=limit, offset=offset)

    async def get(self, registration_id: uuid.UUID) -> EmployeeRegistration:
        return await self._get(registration_id)

    async def approve(
        self,
        registration_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        adjustment: RegistrationAdjustment | None = None,
    ) -> EmployeeRegistration:
        adjustment = adjustment or RegistrationAdjustment()
        async with self._uow:
            registration = await self._get(registration_id)
            department_id = adjustment.department_id or registration.department_id
            team_id = adjustment.team_id if adjustment.team_changed else registration.team_id
            position_id = adjustment.position_id or registration.position_id
            employment_type = adjustment.employment_type or registration.employment_type
            assignments = (
                registration.assignments
                if adjustment.assignments is None
                else adjustment.assignments
            )
            await self._validator.validate(
                department_id=department_id,
                team_id=team_id,
                position_id=position_id,
                assignments=assignments,
                strict=False,
            )
            requested = _snapshot(registration)
            registration.approve(
                now=self._clock.now(),
                department_id=department_id,
                team_id=team_id,
                position_id=position_id,
                employment_type=employment_type,
                assignments=assignments,
            )
            await self._registrations.save(registration)

            employee = await self._upsert_employee(registration)
            await self._add_staff_assignments(employee, registration.assignments)
            for assignment in registration.assignments:
                await self._roles.grant(
                    registration.user_id,
                    *role_scope(
                        assignment.role,
                        bootcamp_id=assignment.bootcamp_id,
                        cohort_id=assignment.cohort_id,
                    ),
                )
            await self._users.approve(registration.user_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="organization.staff_registration.approve",
                target_type="employee_registration",
                target_id=registration.id,
                before=requested,
                after=_snapshot(registration),
            )
        return registration

    async def reject(
        self, registration_id: uuid.UUID, *, actor_id: uuid.UUID, reason: str
    ) -> EmployeeRegistration:
        async with self._uow:
            registration = await self._get(registration_id)
            registration.reject(now=self._clock.now(), reason=reason)
            await self._registrations.save(registration)
            await self._users.mark_rejected(registration.user_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="organization.staff_registration.reject",
                target_type="employee_registration",
                target_id=registration.id,
                after={"reason": registration.reject_reason},
            )
        return registration

    async def _get(self, registration_id: uuid.UUID) -> EmployeeRegistration:
        registration = await self._registrations.get(registration_id)
        if registration is None:
            raise NotFoundError("가입 신청을 찾을 수 없습니다.", code="registration_not_found")
        return registration

    async def _upsert_employee(self, registration: EmployeeRegistration) -> Employee:
        employee = await self._employees.get_by_user(registration.user_id)
        if employee is None:
            employee = Employee(
                user_id=registration.user_id,
                department_id=registration.department_id,
                team_id=registration.team_id,
                position_id=registration.position_id,
                employment_type=registration.employment_type,
            )
            await self._employees.add(employee)
            return employee
        employee.transfer(
            department_id=registration.department_id,
            team_id=registration.team_id,
            position_id=registration.position_id,
        )
        employee.change_employment_type(registration.employment_type)
        await self._employees.save(employee)
        return employee

    async def _add_staff_assignments(
        self, employee: Employee, assignments: list[RequestedAssignment]
    ) -> None:
        bootcamps = {
            (s.bootcamp_id, s.role)
            for s in await self._bootcamp_staffs.list_by_employee(employee.id)
        }
        cohorts = {
            (s.cohort_id, s.role) for s in await self._cohort_staffs.list_by_employee(employee.id)
        }
        for a in assignments:
            if a.bootcamp_id is not None and (a.bootcamp_id, a.role) not in bootcamps:
                await self._bootcamp_staffs.add(
                    BootcampStaff(employee_id=employee.id, bootcamp_id=a.bootcamp_id, role=a.role)
                )
            if a.cohort_id is not None and (a.cohort_id, a.role) not in cohorts:
                await self._cohort_staffs.add(
                    CohortStaff(employee_id=employee.id, cohort_id=a.cohort_id, role=a.role)
                )


def _snapshot(registration: EmployeeRegistration) -> dict[str, object]:
    return {
        "department_id": str(registration.department_id),
        "team_id": str(registration.team_id) if registration.team_id else None,
        "position_id": str(registration.position_id),
        "employment_type": registration.employment_type.value,
        "assignments": [
            {
                "role": a.role.value,
                "bootcamp_id": str(a.bootcamp_id) if a.bootcamp_id else None,
                "cohort_id": str(a.cohort_id) if a.cohort_id else None,
            }
            for a in registration.assignments
        ],
    }

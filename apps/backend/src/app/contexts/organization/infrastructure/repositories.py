"""organization 리포지토리 구현 (Tortoise)."""

import uuid

from app.contexts.organization.domain.entities import (
    BootcampStaff,
    CohortStaff,
    Department,
    Employee,
    EmployeePosition,
)
from app.contexts.organization.domain.enums import EmployeeRegistrationStatus
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.infrastructure.models import (
    BootcampStaffModel,
    CohortStaffModel,
    DepartmentModel,
    EmployeeModel,
    EmployeePositionModel,
    EmployeeRegistrationAssignmentModel,
    EmployeeRegistrationModel,
)
from app.core.persistence import TortoiseRepository


class TortoiseDepartmentRepository(TortoiseRepository[Department, DepartmentModel]):
    model = DepartmentModel
    entity = Department
    fields = ("parent_id", "name", "description", "rules")

    async def list_all(self) -> list[Department]:
        rows = await DepartmentModel.all().order_by("name")
        return [self.to_entity(row) for row in rows]


class TortoiseEmployeePositionRepository(
    TortoiseRepository[EmployeePosition, EmployeePositionModel]
):
    model = EmployeePositionModel
    entity = EmployeePosition
    fields = ("name", "priority")

    async def list_all(self) -> list[EmployeePosition]:
        rows = await EmployeePositionModel.all().order_by("priority", "name")
        return [self.to_entity(row) for row in rows]


class TortoiseEmployeeRepository(TortoiseRepository[Employee, EmployeeModel]):
    model = EmployeeModel
    entity = Employee
    fields = ("user_id", "department_id", "position_id", "employment_type")

    async def get_by_user(self, user_id: uuid.UUID) -> Employee | None:
        row = await EmployeeModel.get_or_none(user_id=user_id)
        return self.to_entity(row) if row else None


class TortoiseBootcampStaffRepository(TortoiseRepository[BootcampStaff, BootcampStaffModel]):
    model = BootcampStaffModel
    entity = BootcampStaff
    fields = ("employee_id", "bootcamp_id", "role", "created_at")

    async def add(self, entity: BootcampStaff) -> None:
        values = self.to_values(entity)
        values.pop("created_at")  # auto_now_add
        row = await BootcampStaffModel.create(id=entity.id, **values)
        entity.created_at = row.created_at

    async def remove(self, staff_id: uuid.UUID) -> None:
        await BootcampStaffModel.filter(id=staff_id).delete()

    async def list_by_bootcamp(self, bootcamp_id: uuid.UUID) -> list[BootcampStaff]:
        rows = await BootcampStaffModel.filter(bootcamp_id=bootcamp_id).order_by("role", "id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employee(self, employee_id: uuid.UUID) -> list[BootcampStaff]:
        rows = await BootcampStaffModel.filter(employee_id=employee_id).order_by("id")
        return [self.to_entity(row) for row in rows]


class TortoiseCohortStaffRepository(TortoiseRepository[CohortStaff, CohortStaffModel]):
    model = CohortStaffModel
    entity = CohortStaff
    fields = ("employee_id", "cohort_id", "role", "created_at")

    async def add(self, entity: CohortStaff) -> None:
        values = self.to_values(entity)
        values.pop("created_at")  # auto_now_add
        row = await CohortStaffModel.create(id=entity.id, **values)
        entity.created_at = row.created_at

    async def remove(self, staff_id: uuid.UUID) -> None:
        await CohortStaffModel.filter(id=staff_id).delete()

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[CohortStaff]:
        rows = await CohortStaffModel.filter(cohort_id=cohort_id).order_by("role", "id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employee(self, employee_id: uuid.UUID) -> list[CohortStaff]:
        rows = await CohortStaffModel.filter(employee_id=employee_id).order_by("id")
        return [self.to_entity(row) for row in rows]


class TortoiseEmployeeRegistrationRepository(
    TortoiseRepository[EmployeeRegistration, EmployeeRegistrationModel]
):
    """신청과 담당 목록을 함께 저장·조회한다. 담당 목록은 저장할 때마다 통째로 바꾼다."""

    model = EmployeeRegistrationModel
    entity = EmployeeRegistration
    fields = (
        "user_id",
        "department_id",
        "position_id",
        "employment_type",
        "status",
        "reviewed_at",
        "reject_reason",
    )

    async def add(self, entity: EmployeeRegistration) -> None:
        row = await EmployeeRegistrationModel.create(id=entity.id, **self.to_values(entity))
        entity.created_at = row.created_at
        await self._replace_assignments(entity)

    async def save(self, entity: EmployeeRegistration) -> None:
        await super().save(entity)
        await self._replace_assignments(entity)

    async def get(self, entity_id: uuid.UUID) -> EmployeeRegistration | None:
        row = await EmployeeRegistrationModel.get_or_none(id=entity_id).prefetch_related(
            "assignments"
        )
        return self._to_aggregate(row) if row else None

    async def get_latest_by_user(self, user_id: uuid.UUID) -> EmployeeRegistration | None:
        row = (
            await EmployeeRegistrationModel.filter(user_id=user_id)
            .order_by("-created_at", "-id")
            .prefetch_related("assignments")
            .first()
        )
        return self._to_aggregate(row) if row else None

    async def list_by_status(
        self, status: EmployeeRegistrationStatus, *, limit: int, offset: int
    ) -> tuple[list[EmployeeRegistration], int]:
        query = EmployeeRegistrationModel.filter(status=status)
        rows = (
            await query.order_by("created_at", "id")
            .offset(offset)
            .limit(limit)
            .prefetch_related("assignments")
        )
        return [self._to_aggregate(row) for row in rows], await query.count()

    def _to_aggregate(self, row: EmployeeRegistrationModel) -> EmployeeRegistration:
        registration = self.to_entity(row)
        registration.created_at = row.created_at
        registration.assignments = [
            RequestedAssignment(
                role=a.role,
                bootcamp_id=a.bootcamp_id,  # type: ignore[attr-defined]  # Tortoise FK 컬럼 속성
                cohort_id=a.cohort_id,  # type: ignore[attr-defined]
            )
            for a in sorted(row.assignments, key=lambda a: a.id)  # uuid7 = 저장 순서
        ]
        return registration

    async def _replace_assignments(self, entity: EmployeeRegistration) -> None:
        await EmployeeRegistrationAssignmentModel.filter(registration_id=entity.id).delete()
        await EmployeeRegistrationAssignmentModel.bulk_create(
            [
                EmployeeRegistrationAssignmentModel(
                    registration_id=entity.id,
                    role=a.role,
                    bootcamp_id=a.bootcamp_id,
                    cohort_id=a.cohort_id,
                )
                for a in entity.assignments
            ]
        )

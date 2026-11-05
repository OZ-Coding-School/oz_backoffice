"""organization 리포지토리 구현 (Tortoise)."""

import uuid

from app.contexts.organization.domain.entities import (
    BootcampStaff,
    CohortStaff,
    Department,
    Employee,
    EmployeePosition,
)
from app.contexts.organization.infrastructure.models import (
    BootcampStaffModel,
    CohortStaffModel,
    DepartmentModel,
    EmployeeModel,
    EmployeePositionModel,
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

"""organization 리포지토리 구현 (Tortoise)."""

import uuid

from tortoise.expressions import Q

from app.contexts.organization.domain.entities import (
    BootcampStaff,
    BootcampTeam,
    CohortStaff,
    Department,
    Employee,
    EmployeePosition,
    Team,
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
    PositionPermissionModel,
    TeamBootcampModel,
    TeamModel,
)
from app.core.persistence import TortoiseRepository


class TortoiseDepartmentRepository(TortoiseRepository[Department, DepartmentModel]):
    model = DepartmentModel
    entity = Department
    fields = ("name", "description", "rules")

    async def get_by_name(self, name: str) -> Department | None:
        row = await DepartmentModel.get_or_none(name=name.strip())
        return self.to_entity(row) if row else None

    async def list_all(self) -> list[Department]:
        rows = await DepartmentModel.all().order_by("name")
        return [self.to_entity(row) for row in rows]


class TortoiseTeamRepository(TortoiseRepository[Team, TeamModel]):
    model = TeamModel
    entity = Team
    fields = ("department_id", "name", "description")

    async def is_referenced(self, team_id: uuid.UUID) -> bool:
        return (
            await EmployeeModel.filter(team_id=team_id).exists()
            or await EmployeeRegistrationModel.filter(team_id=team_id).exists()
            or await TeamBootcampModel.filter(team_id=team_id).exists()
        )

    async def move_references(self, from_team_id: uuid.UUID, to_team_id: uuid.UUID) -> None:
        await EmployeeModel.filter(team_id=from_team_id).update(team_id=to_team_id)
        await EmployeeRegistrationModel.filter(team_id=from_team_id).update(team_id=to_team_id)
        await TeamBootcampModel.filter(team_id=from_team_id).update(team_id=to_team_id)

    async def find_by_department_and_name(self, department_id: uuid.UUID, name: str) -> Team | None:
        row = await TeamModel.get_or_none(department_id=department_id, name=name.strip())
        return self.to_entity(row) if row else None

    async def list_all(self) -> list[Team]:
        rows = await TeamModel.all().order_by("name", "id")
        return [self.to_entity(row) for row in rows]


class TortoiseBootcampTeamRepository:
    async def assign(self, bootcamp_id: uuid.UUID, team_id: uuid.UUID | None) -> None:
        if team_id is None:
            await TeamBootcampModel.filter(bootcamp_id=bootcamp_id).delete()
            return
        updated = await TeamBootcampModel.filter(bootcamp_id=bootcamp_id).update(team_id=team_id)
        if not updated:
            await TeamBootcampModel.create(bootcamp_id=bootcamp_id, team_id=team_id)

    async def get(self, bootcamp_id: uuid.UUID) -> BootcampTeam | None:
        row = await TeamBootcampModel.get_or_none(bootcamp_id=bootcamp_id)
        return _bootcamp_team(row) if row else None

    async def list_all(self) -> list[BootcampTeam]:
        return [_bootcamp_team(row) for row in await TeamBootcampModel.all().order_by("id")]

    async def list_bootcamp_ids(self, team_id: uuid.UUID) -> set[uuid.UUID]:
        ids = await TeamBootcampModel.filter(team_id=team_id).values_list("bootcamp_id", flat=True)
        return {uuid.UUID(str(i)) for i in ids}


def _bootcamp_team(row: TeamBootcampModel) -> BootcampTeam:
    return BootcampTeam(
        bootcamp_id=row.bootcamp_id,  # type: ignore[attr-defined]  # Tortoise FK 컬럼 속성
        team_id=row.team_id,  # type: ignore[attr-defined]
    )


class TortoiseEmployeePositionRepository(
    TortoiseRepository[EmployeePosition, EmployeePositionModel]
):
    model = EmployeePositionModel
    entity = EmployeePosition
    fields = ("name", "priority", "assignment_scope", "data_scope")

    async def get_by_name(self, name: str) -> EmployeePosition | None:
        row = await EmployeePositionModel.get_or_none(name=name.strip())
        return self.to_entity(row) if row else None

    async def list_all(self) -> list[EmployeePosition]:
        rows = await EmployeePositionModel.all().order_by("priority", "name")
        return [self.to_entity(row) for row in rows]

    async def permissions_of(self, position_id: uuid.UUID) -> frozenset[str]:
        codes = await PositionPermissionModel.filter(position_id=position_id).values_list(
            "permission_code", flat=True
        )
        return frozenset(str(c) for c in codes)

    async def permissions_by_position(self) -> dict[uuid.UUID, frozenset[str]]:
        result: dict[uuid.UUID, set[str]] = {}
        for position_id, code in await PositionPermissionModel.all().values_list(
            "position_id", "permission_code"
        ):
            result.setdefault(uuid.UUID(str(position_id)), set()).add(str(code))
        return {k: frozenset(v) for k, v in result.items()}

    async def replace_permissions(self, position_id: uuid.UUID, codes: frozenset[str]) -> None:
        current = await self.permissions_of(position_id)
        removed = current - codes
        if removed:
            await PositionPermissionModel.filter(
                position_id=position_id, permission_code__in=sorted(removed)
            ).delete()
        added = codes - current
        if added:
            await PositionPermissionModel.bulk_create(
                [
                    PositionPermissionModel(position_id=position_id, permission_code=code)
                    for code in sorted(added)
                ]
            )


class TortoiseEmployeeRepository(TortoiseRepository[Employee, EmployeeModel]):
    model = EmployeeModel
    entity = Employee
    fields = ("user_id", "department_id", "team_id", "position_id", "employment_type")

    async def get_by_user(self, user_id: uuid.UUID) -> Employee | None:
        row = await EmployeeModel.get_or_none(user_id=user_id)
        return self.to_entity(row) if row else None

    async def search(
        self,
        *,
        department_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        query: str | None = None,
    ) -> list[Employee]:
        rows_query = EmployeeModel.all()
        if department_id is not None:
            rows_query = rows_query.filter(department_id=department_id)
        if team_id is not None:
            rows_query = rows_query.filter(team_id=team_id)
        if query:
            rows_query = rows_query.filter(
                Q(user__name__icontains=query) | Q(user__email__icontains=query)
            )
        rows = await rows_query.order_by("created_at", "id")
        return [self.to_entity(row) for row in rows]

    async def list_by_ids(self, employee_ids: list[uuid.UUID]) -> list[Employee]:
        if not employee_ids:
            return []
        return [self.to_entity(row) for row in await EmployeeModel.filter(id__in=employee_ids)]

    async def list_by_users(self, user_ids: list[uuid.UUID]) -> list[Employee]:
        if not user_ids:
            return []
        return [self.to_entity(row) for row in await EmployeeModel.filter(user_id__in=user_ids)]

    async def count_by_org(self) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        departments: dict[uuid.UUID, int] = {}
        teams: dict[uuid.UUID, int] = {}
        for department_id, team_id in await EmployeeModel.all().values_list(
            "department_id", "team_id"
        ):
            d = uuid.UUID(str(department_id))
            departments[d] = departments.get(d, 0) + 1
            if team_id is not None:
                t = uuid.UUID(str(team_id))
                teams[t] = teams.get(t, 0) + 1
        return departments, teams

    async def count_by_position(self) -> dict[uuid.UUID, int]:
        counts: dict[uuid.UUID, int] = {}
        for position_id in await EmployeeModel.all().values_list("position_id", flat=True):
            key = uuid.UUID(str(position_id))
            counts[key] = counts.get(key, 0) + 1
        return counts


class TortoiseBootcampStaffRepository(TortoiseRepository[BootcampStaff, BootcampStaffModel]):
    model = BootcampStaffModel
    entity = BootcampStaff
    fields = ("employee_id", "bootcamp_id", "created_at")

    async def add(self, entity: BootcampStaff) -> None:
        values = self.to_values(entity)
        values.pop("created_at")  # auto_now_add
        row = await BootcampStaffModel.create(id=entity.id, **values)
        entity.created_at = row.created_at

    async def remove(self, staff_id: uuid.UUID) -> None:
        await BootcampStaffModel.filter(id=staff_id).delete()

    async def list_by_bootcamp(self, bootcamp_id: uuid.UUID) -> list[BootcampStaff]:
        rows = await BootcampStaffModel.filter(bootcamp_id=bootcamp_id).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employee(self, employee_id: uuid.UUID) -> list[BootcampStaff]:
        rows = await BootcampStaffModel.filter(employee_id=employee_id).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employees(self, employee_ids: list[uuid.UUID]) -> list[BootcampStaff]:
        if not employee_ids:
            return []
        rows = await BootcampStaffModel.filter(employee_id__in=employee_ids).order_by("id")
        return [self.to_entity(row) for row in rows]


class TortoiseCohortStaffRepository(TortoiseRepository[CohortStaff, CohortStaffModel]):
    model = CohortStaffModel
    entity = CohortStaff
    fields = ("employee_id", "cohort_id", "created_at")

    async def add(self, entity: CohortStaff) -> None:
        values = self.to_values(entity)
        values.pop("created_at")  # auto_now_add
        row = await CohortStaffModel.create(id=entity.id, **values)
        entity.created_at = row.created_at

    async def remove(self, staff_id: uuid.UUID) -> None:
        await CohortStaffModel.filter(id=staff_id).delete()

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[CohortStaff]:
        rows = await CohortStaffModel.filter(cohort_id=cohort_id).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employee(self, employee_id: uuid.UUID) -> list[CohortStaff]:
        rows = await CohortStaffModel.filter(employee_id=employee_id).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_by_employees(self, employee_ids: list[uuid.UUID]) -> list[CohortStaff]:
        if not employee_ids:
            return []
        rows = await CohortStaffModel.filter(employee_id__in=employee_ids).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def staffed_cohort_ids(self) -> set[uuid.UUID]:
        ids = await CohortStaffModel.all().distinct().values_list("cohort_id", flat=True)
        return {uuid.UUID(str(i)) for i in ids}


class TortoiseEmployeeRegistrationRepository(
    TortoiseRepository[EmployeeRegistration, EmployeeRegistrationModel]
):
    """신청과 담당 목록을 함께 저장·조회한다. 담당 목록은 저장할 때마다 통째로 바꾼다."""

    model = EmployeeRegistrationModel
    entity = EmployeeRegistration
    fields = (
        "user_id",
        "department_id",
        "team_id",
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
                    bootcamp_id=a.bootcamp_id,
                    cohort_id=a.cohort_id,
                )
                for a in entity.assignments
            ]
        )

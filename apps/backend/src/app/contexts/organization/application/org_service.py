"""조직 마스터 관리 (부서·팀·직위·직원). 권한 org.manage (decisions D5: 부서는 조직도 용도).

- 부서: 이름 유일, 팀·직원·신청이 참조 중이면 삭제 불가
- 팀: 한 부서 소속(다른 부서로 옮길 수 있음), 부서 안에서 이름 유일.
  지울 때 직원·신청·담당 과정의 참조를 이동할 팀으로 옮긴다 (A62)
- 과정 담당 팀: 과정당 한 팀, 관리자가 바꾼다 (A62)
- 직위: 이름 유일, 담당 방식(COURSE·COHORT·없음), 직원이 쓰는 직위는 삭제 불가
- 직원: 가입 승인(P3-2b)으로 만들어진다. 여기서는 조회와 부서·직위·고용 형태 이동만 한다
모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.contexts.academy.domain.entities import Bootcamp
from app.contexts.access.domain.catalog import validate_permissions
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.organization.application.registration_service import StaffTargetCatalog
from app.contexts.organization.domain.entities import (
    BootcampStaff,
    CohortStaff,
    Department,
    Employee,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope, DataScope, EmploymentType
from app.contexts.organization.domain.registration import check_employee_assignments
from app.contexts.organization.domain.repositories import (
    BootcampStaffRepository,
    BootcampTeamRepository,
    CohortStaffRepository,
    DepartmentRepository,
    EmployeePositionRepository,
    EmployeeRepository,
    TeamRepository,
)
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError

_UNSET: Any = object()


class BootcampLookup(Protocol):
    """academy `AcademyCatalog`가 구현."""

    async def get_bootcamp(self, bootcamp_id: uuid.UUID) -> Bootcamp | None: ...


def _snapshot(entity: object) -> dict[str, Any]:
    return {
        k: str(v) if isinstance(v, uuid.UUID) else v
        for k, v in vars(entity).items()
        if not k.startswith("_") and k != "id"
    }


@dataclass(frozen=True, slots=True)
class PositionView:
    """직위 + 권한 묶음 + 직원 수 (A87)."""

    position: EmployeePosition
    permissions: frozenset[str]
    employee_count: int


@dataclass(frozen=True, slots=True)
class DepartmentChanges:
    """부서 수정 항목. 보내지 않은 항목은 _UNSET(그대로)."""

    name: str = _UNSET
    description: str = _UNSET
    rules: str | None = _UNSET


@dataclass(frozen=True, slots=True)
class TeamChanges:
    """팀 수정 항목. 보내지 않은 항목은 _UNSET(그대로)."""

    department_id: uuid.UUID = _UNSET
    name: str = _UNSET
    description: str | None = _UNSET


@dataclass(frozen=True, slots=True)
class PositionChanges:
    """직위 수정 항목. 보내지 않은 항목은 _UNSET(그대로). 담당 방식은 None(담당 없음) 가능."""

    name: str = _UNSET
    priority: int = _UNSET
    assignment_scope: AssignmentScope | None = _UNSET
    data_scope: DataScope = _UNSET


@dataclass(frozen=True, slots=True)
class EmployeeChanges:
    """직원 수정 항목. 보내지 않은 항목은 _UNSET(그대로). 팀은 None(부서 직속)으로 바꿀 수 있다."""

    department_id: uuid.UUID = _UNSET
    team_id: uuid.UUID | None = _UNSET
    position_id: uuid.UUID = _UNSET
    employment_type: EmploymentType = _UNSET
    bootcamp_ids: list[uuid.UUID] = _UNSET  # 보내면 담당 과정을 통째로 바꾼다 (A89)
    cohort_ids: list[uuid.UUID] = _UNSET  # 보내면 담당 기수를 통째로 바꾼다


class OrganizationAdminService:
    def __init__(
        self,
        *,
        departments: DepartmentRepository,
        teams: TeamRepository,
        bootcamp_teams: BootcampTeamRepository,
        bootcamps: BootcampLookup,
        positions: EmployeePositionRepository,
        employees: EmployeeRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
        bootcamp_staffs: BootcampStaffRepository | None = None,
        cohort_staffs: CohortStaffRepository | None = None,
        staff_targets: StaffTargetCatalog | None = None,
    ) -> None:
        self._departments = departments
        self._teams = teams
        self._bootcamp_teams = bootcamp_teams
        self._bootcamps = bootcamps
        self._positions = positions
        self._employees = employees
        self._audit = audit
        self._uow = uow
        self._bootcamp_staffs = bootcamp_staffs
        self._cohort_staffs = cohort_staffs
        self._staff_targets = staff_targets

    # ------------------------------------------------------------------ 부서
    async def list_departments(self) -> list[Department]:
        return await self._departments.list_all()

    async def employee_counts(self) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int]]:
        """(부서별, 팀별) 직원 수 (A92)."""
        return await self._employees.count_by_org()

    async def create_department(
        self, *, name: str, description: str, rules: str | None, actor_id: uuid.UUID
    ) -> Department:
        department = Department(name=name, description=description, rules=rules)
        async with self._uow:
            await self._ensure_department_name_free(department.name)
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
            department.update(
                name=department.name if changes.name is _UNSET else changes.name,
                description=department.description
                if changes.description is _UNSET
                else changes.description,
                rules=department.rules if changes.rules is _UNSET else changes.rules,
            )
            if department.name != before["name"]:
                await self._ensure_department_name_free(department.name)
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
            await self._departments.delete(department_id)  # 팀·직원·신청이 참조 중이면 409
            await self._record(
                actor_id, "department.delete", department, before=_snapshot(department)
            )

    # ------------------------------------------------------------------ 팀
    async def list_teams(self) -> list[tuple[Team, list[uuid.UUID]]]:
        """팀과 각 팀이 담당하는 과정 id."""
        bootcamps: dict[uuid.UUID, list[uuid.UUID]] = {}
        for link in await self._bootcamp_teams.list_all():
            bootcamps.setdefault(link.team_id, []).append(link.bootcamp_id)
        return [(team, bootcamps.get(team.id, [])) for team in await self._teams.list_all()]

    async def create_team(
        self,
        *,
        department_id: uuid.UUID,
        name: str,
        description: str | None,
        actor_id: uuid.UUID,
    ) -> Team:
        team = Team(department_id=department_id, name=name, description=description)
        async with self._uow:
            await self._get_department(department_id)
            await self._ensure_team_name_free(department_id, team.name)
            await self._teams.add(team)
            await self._record(actor_id, "team.create", team, after=_snapshot(team))
        return team

    async def update_team(
        self, team_id: uuid.UUID, changes: TeamChanges, *, actor_id: uuid.UUID
    ) -> Team:
        async with self._uow:
            team = await self._get_team(team_id)
            before = _snapshot(team)
            department_id = (
                team.department_id if changes.department_id is _UNSET else changes.department_id
            )
            if department_id != team.department_id:
                await self._get_department(department_id)
            team.update(
                department_id=department_id,
                name=team.name if changes.name is _UNSET else changes.name,
                description=team.description
                if changes.description is _UNSET
                else changes.description,
            )
            if (str(team.department_id), team.name) != (before["department_id"], before["name"]):
                await self._ensure_team_name_free(team.department_id, team.name, exclude=team.id)
            await self._teams.save(team)
            await self._record(actor_id, "team.update", team, before=before, after=_snapshot(team))
        return team

    async def delete_team(
        self,
        team_id: uuid.UUID,
        *,
        move_to_team_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> None:
        """팀을 지운다 (A62).

        직원·가입 신청(이력 포함)·담당 과정이 참조 중이면 이동할 팀을 받아 한 트랜잭션에서
        참조를 그 팀으로 옮긴 뒤 지운다. 이동할 팀 없이 참조가 남아 있으면 409 `team_in_use`.
        """
        async with self._uow:
            team = await self._get_team(team_id)
            moved_to: Team | None = None
            if move_to_team_id is not None:
                if move_to_team_id == team_id:
                    raise BusinessRuleViolation(
                        "지울 팀과 다른 팀으로 옮겨야 합니다.", code="invalid_move_to_team"
                    )
                moved_to = await self._get_team(move_to_team_id)
                await self._teams.move_references(team_id, moved_to.id)
            elif await self._teams.is_referenced(team_id):
                raise ConflictError(
                    "직원·가입 신청·담당 과정이 있는 팀입니다. 옮길 팀을 지정해 주세요.",
                    code="team_in_use",
                )
            await self._teams.delete(team_id)
            await self._record(
                actor_id,
                "team.delete",
                team,
                before=_snapshot(team),
                after={"moved_to_team_id": _str(moved_to.id if moved_to else None)},
            )

    async def set_bootcamp_team(
        self, bootcamp_id: uuid.UUID, team_id: uuid.UUID | None, *, actor_id: uuid.UUID
    ) -> uuid.UUID | None:
        """과정의 담당 팀을 정한다. None이면 담당 팀을 없앤다 (A62)."""
        if await self._bootcamps.get_bootcamp(bootcamp_id) is None:
            raise NotFoundError("과정을 찾을 수 없습니다.", code="bootcamp_not_found")
        async with self._uow:
            if team_id is not None:
                await self._get_team(team_id)
            current = await self._bootcamp_teams.get(bootcamp_id)
            before = current.team_id if current else None
            if before != team_id:
                await self._bootcamp_teams.assign(bootcamp_id, team_id)
                await self._audit.record(
                    actor_user_id=actor_id,
                    action="organization.bootcamp_team.set",
                    target_type="bootcamp",
                    target_id=bootcamp_id,
                    before={"team_id": _str(before)},
                    after={"team_id": _str(team_id)},
                )
        return team_id

    # ------------------------------------------------------------------ 직위 (= 역할, A87)
    async def list_positions(self) -> list[PositionView]:
        permissions = await self._positions.permissions_by_position()
        counts = await self._employees.count_by_position()
        return [
            PositionView(p, permissions.get(p.id, frozenset()), counts.get(p.id, 0))
            for p in await self._positions.list_all()
        ]

    async def get_position(self, position_id: uuid.UUID) -> PositionView:
        position = await self._get_position(position_id)
        counts = await self._employees.count_by_position()
        return PositionView(
            position, await self._positions.permissions_of(position_id), counts.get(position_id, 0)
        )

    async def create_position(
        self,
        *,
        name: str,
        priority: int,
        assignment_scope: AssignmentScope | None,
        actor_id: uuid.UUID,
        data_scope: DataScope = DataScope.ASSIGNED,
    ) -> EmployeePosition:
        position = EmployeePosition(
            name=name, priority=priority, assignment_scope=assignment_scope, data_scope=data_scope
        )
        async with self._uow:
            await self._ensure_position_name_free(position.name)
            await self._positions.add(position)
            await self._record(actor_id, "position.create", position, after=_snapshot(position))
        return position

    async def update_position(
        self, position_id: uuid.UUID, changes: PositionChanges, *, actor_id: uuid.UUID
    ) -> EmployeePosition:
        async with self._uow:
            position = await self._get_position(position_id)
            before = _snapshot(position)
            position.update(
                name=position.name if changes.name is _UNSET else changes.name,
                priority=position.priority if changes.priority is _UNSET else changes.priority,
                assignment_scope=position.assignment_scope
                if changes.assignment_scope is _UNSET
                else changes.assignment_scope,
                data_scope=None if changes.data_scope is _UNSET else changes.data_scope,
            )
            if position.name != before["name"]:
                await self._ensure_position_name_free(position.name)
            await self._positions.save(position)
            await self._record(
                actor_id, "position.update", position, before=before, after=_snapshot(position)
            )
        return position

    async def replace_position_permissions(
        self, position_id: uuid.UUID, codes: list[str], *, actor_id: uuid.UUID
    ) -> PositionView:
        """직위의 권한 묶음을 통째로 바꾼다 (A87). 관리는 조회와 함께 (A86)."""
        wanted = validate_permissions(codes)
        async with self._uow:
            position = await self._get_position(position_id)
            before = await self._positions.permissions_of(position_id)
            await self._positions.replace_permissions(position_id, wanted)
            await self._record(
                actor_id,
                "position.permissions",
                position,
                before={"permissions": sorted(before)},
                after={"permissions": sorted(wanted)},
            )
        return await self.get_position(position_id)

    async def delete_position(self, position_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            position = await self._get_position(position_id)
            await self._positions.delete(position_id)  # 직원·신청이 쓰는 직위면 409
            await self._record(actor_id, "position.delete", position, before=_snapshot(position))

    # ------------------------------------------------------------------ 직원
    async def list_employees(
        self,
        *,
        department_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        query: str | None = None,
    ) -> list[Employee]:
        """직원 전체 (A90: 화면이 부서·팀별로 묶는다)."""
        return await self._employees.search(
            department_id=department_id, team_id=team_id, query=(query or "").strip() or None
        )

    async def get_employee(self, employee_id: uuid.UUID) -> Employee:
        employee = await self._employees.get(employee_id)
        if employee is None:
            raise NotFoundError("직원을 찾을 수 없습니다.", code="employee_not_found")
        return employee

    async def update_employee(
        self, employee_id: uuid.UUID, changes: EmployeeChanges, *, actor_id: uuid.UUID
    ) -> Employee:
        """관리자 이동은 존재만 검사한다 (A62: 담당 규칙은 신청할 때만)."""
        async with self._uow:
            employee = await self.get_employee(employee_id)
            before = _snapshot(employee)
            if changes.department_id is not _UNSET:
                await self._get_department(changes.department_id)
            if changes.team_id not in (_UNSET, None):
                await self._get_team(changes.team_id)
            if changes.position_id is not _UNSET:
                await self._get_position(changes.position_id)
            employee.transfer(
                department_id=employee.department_id
                if changes.department_id is _UNSET
                else changes.department_id,
                team_id=employee.team_id if changes.team_id is _UNSET else changes.team_id,
                position_id=employee.position_id
                if changes.position_id is _UNSET
                else changes.position_id,
            )
            if changes.employment_type is not _UNSET:
                employee.change_employment_type(changes.employment_type)
            await self._employees.save(employee)
            await self._record(
                actor_id, "employee.update", employee, before=before, after=_snapshot(employee)
            )
            if changes.bootcamp_ids is not _UNSET or changes.cohort_ids is not _UNSET:
                await self._replace_assignments(employee, changes, actor_id)
        return employee

    async def _replace_assignments(
        self, employee: Employee, changes: EmployeeChanges, actor_id: uuid.UUID
    ) -> None:
        """담당을 직위의 담당 방식대로 통째로 바꾼다 (A89). 보내지 않은 쪽은 비운다."""
        if self._bootcamp_staffs is None or self._cohort_staffs is None or not self._staff_targets:
            raise RuntimeError("담당을 바꾸려면 담당자 저장소가 필요합니다.")
        bootcamp_ids = [] if changes.bootcamp_ids is _UNSET else list(changes.bootcamp_ids)
        cohort_ids = [] if changes.cohort_ids is _UNSET else list(changes.cohort_ids)
        position = await self._get_position(employee.position_id)
        current_b = await self._bootcamp_staffs.list_by_employee(employee.id)
        current_c = await self._cohort_staffs.list_by_employee(employee.id)
        mine = {s.cohort_id for s in current_c}
        check_employee_assignments(
            position.assignment_scope,
            bootcamp_ids=bootcamp_ids,
            cohort_ids=cohort_ids,
            taken_cohort_ids=await self._cohort_staffs.staffed_cohort_ids() - mine,
        )
        await self._staff_targets.ensure_staffable(
            bootcamp_ids=[b for b in bootcamp_ids if b not in {s.bootcamp_id for s in current_b}],
            cohort_ids=[c for c in cohort_ids if c not in mine],
        )
        for s in current_b:
            if s.bootcamp_id not in bootcamp_ids:
                await self._bootcamp_staffs.remove(s.id)
        for staff in current_c:
            if staff.cohort_id not in cohort_ids:
                await self._cohort_staffs.remove(staff.id)
        for b in bootcamp_ids:
            if b not in {s.bootcamp_id for s in current_b}:
                await self._bootcamp_staffs.add(
                    BootcampStaff(employee_id=employee.id, bootcamp_id=b)
                )
        for c in cohort_ids:
            if c not in mine:
                await self._cohort_staffs.add(CohortStaff(employee_id=employee.id, cohort_id=c))
        await self._audit.record(
            actor_user_id=actor_id,
            action="organization.employee.assignments",
            target_type="employee",
            target_id=employee.id,
            before={
                "bootcamp_ids": sorted(str(s.bootcamp_id) for s in current_b),
                "cohort_ids": sorted(str(s.cohort_id) for s in current_c),
            },
            after={
                "bootcamp_ids": sorted(str(b) for b in bootcamp_ids),
                "cohort_ids": sorted(str(c) for c in cohort_ids),
            },
        )

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

    async def _get_team(self, team_id: uuid.UUID) -> Team:
        team = await self._teams.get(team_id)
        if team is None:
            raise NotFoundError("팀을 찾을 수 없습니다.", code="team_not_found")
        return team

    async def _ensure_department_name_free(self, name: str) -> None:
        if await self._departments.get_by_name(name) is not None:
            raise ConflictError("같은 이름의 부서가 있습니다.", code="department_name_taken")

    async def _ensure_team_name_free(
        self, department_id: uuid.UUID, name: str, *, exclude: uuid.UUID | None = None
    ) -> None:
        existing = await self._teams.find_by_department_and_name(department_id, name)
        if existing is not None and existing.id != exclude:
            raise ConflictError("같은 부서에 같은 이름의 팀이 있습니다.", code="team_name_taken")

    async def _ensure_position_name_free(self, name: str) -> None:
        if await self._positions.get_by_name(name) is not None:
            raise ConflictError("같은 이름의 직위가 있습니다.", code="position_name_taken")

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        entity: Department | Team | EmployeePosition | Employee,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        target = {
            "department": "department",
            "team": "team",
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

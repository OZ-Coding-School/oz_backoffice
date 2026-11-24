"""organization 인메모리 리포지토리와 담당 선택지 가짜 구현."""

import uuid
from collections.abc import Iterable
from dataclasses import replace

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.organization.domain.entities import (
    BootcampTeam,
    CohortStaff,
    Department,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import EmployeeRegistrationStatus, StaffRole
from app.contexts.organization.domain.registration import EmployeeRegistration
from app.shared.errors import BusinessRuleViolation


class InMemoryDepartmentRepository:
    def __init__(self, *departments: Department) -> None:
        self.items = {d.id: d for d in departments}

    async def add(self, department: Department) -> None:
        self.items[department.id] = department

    async def save(self, department: Department) -> None:
        self.items[department.id] = department

    async def get(self, entity_id: uuid.UUID) -> Department | None:
        return self.items.get(entity_id)

    async def delete(self, entity_id: uuid.UUID) -> None:
        self.items.pop(entity_id, None)

    async def get_by_name(self, name: str) -> Department | None:
        return next((d for d in self.items.values() if d.name == name.strip()), None)

    async def list_all(self) -> list[Department]:
        return sorted(self.items.values(), key=lambda d: d.name)


class InMemoryTeamRepository:
    def __init__(self, *teams: Team) -> None:
        self.items = {t.id: t for t in teams}
        self.referenced: set[uuid.UUID] = set()  # 직원·신청·과정이 참조 중인 팀

    async def is_referenced(self, team_id: uuid.UUID) -> bool:
        return team_id in self.referenced

    async def move_references(self, from_team_id: uuid.UUID, to_team_id: uuid.UUID) -> None:
        if from_team_id in self.referenced:
            self.referenced.discard(from_team_id)
            self.referenced.add(to_team_id)

    async def add(self, team: Team) -> None:
        self.items[team.id] = team

    async def save(self, team: Team) -> None:
        self.items[team.id] = team

    async def get(self, entity_id: uuid.UUID) -> Team | None:
        return self.items.get(entity_id)

    async def delete(self, entity_id: uuid.UUID) -> None:
        self.items.pop(entity_id, None)

    async def find_by_department_and_name(self, department_id: uuid.UUID, name: str) -> Team | None:
        return next(
            (
                t
                for t in self.items.values()
                if t.department_id == department_id and t.name == name.strip()
            ),
            None,
        )

    async def list_all(self) -> list[Team]:
        return sorted(self.items.values(), key=lambda t: t.name)


class InMemoryBootcampTeamRepository:
    def __init__(self, *links: BootcampTeam) -> None:
        self.items = {link.bootcamp_id: link for link in links}

    async def assign(self, bootcamp_id: uuid.UUID, team_id: uuid.UUID | None) -> None:
        if team_id is None:
            self.items.pop(bootcamp_id, None)
        else:
            self.items[bootcamp_id] = BootcampTeam(bootcamp_id=bootcamp_id, team_id=team_id)

    async def get(self, bootcamp_id: uuid.UUID) -> BootcampTeam | None:
        return self.items.get(bootcamp_id)

    async def list_all(self) -> list[BootcampTeam]:
        return list(self.items.values())

    async def list_bootcamp_ids(self, team_id: uuid.UUID) -> set[uuid.UUID]:
        return {link.bootcamp_id for link in self.items.values() if link.team_id == team_id}


class InMemoryEmployeePositionRepository:
    def __init__(self, *positions: EmployeePosition) -> None:
        self.items = {p.id: p for p in positions}

    async def add(self, position: EmployeePosition) -> None:
        self.items[position.id] = position

    async def save(self, position: EmployeePosition) -> None:
        self.items[position.id] = position

    async def get(self, entity_id: uuid.UUID) -> EmployeePosition | None:
        return self.items.get(entity_id)

    async def delete(self, entity_id: uuid.UUID) -> None:
        self.items.pop(entity_id, None)

    async def get_by_name(self, name: str) -> EmployeePosition | None:
        return next((p for p in self.items.values() if p.name == name.strip()), None)

    async def list_all(self) -> list[EmployeePosition]:
        return sorted(self.items.values(), key=lambda p: (p.priority, p.name))


class InMemoryEmployeeRegistrationRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, EmployeeRegistration] = {}

    async def add(self, registration: EmployeeRegistration) -> None:
        self.items[registration.id] = replace(registration)

    async def save(self, registration: EmployeeRegistration) -> None:
        self.items[registration.id] = replace(registration)

    async def get(self, entity_id: uuid.UUID) -> EmployeeRegistration | None:
        item = self.items.get(entity_id)
        return replace(item) if item else None

    async def get_latest_by_user(self, user_id: uuid.UUID) -> EmployeeRegistration | None:
        mine = [r for r in self.items.values() if r.user_id == user_id]
        return replace(max(mine, key=lambda r: r.id)) if mine else None  # uuid7 = 생성 순서

    async def list_by_status(
        self, status: EmployeeRegistrationStatus, *, limit: int, offset: int
    ) -> tuple[list[EmployeeRegistration], int]:
        matched = sorted((r for r in self.items.values() if r.status is status), key=lambda r: r.id)
        return [replace(r) for r in matched[offset : offset + limit]], len(matched)


class InMemoryCohortStaffRepository:
    def __init__(self, *staffs: CohortStaff) -> None:
        self.items = {s.id: s for s in staffs}

    async def list_by_employees(self, employee_ids: list[uuid.UUID]) -> list[CohortStaff]:
        return [s for s in self.items.values() if s.employee_id in employee_ids]

    async def add(self, staff: CohortStaff) -> None:
        self.items[staff.id] = staff

    async def remove(self, staff_id: uuid.UUID) -> None:
        self.items.pop(staff_id, None)

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[CohortStaff]:
        return [s for s in self.items.values() if s.cohort_id == cohort_id]

    async def list_by_employee(self, employee_id: uuid.UUID) -> list[CohortStaff]:
        return [s for s in self.items.values() if s.employee_id == employee_id]

    async def cohort_ids_with_role(self, role: StaffRole) -> set[uuid.UUID]:
        return {s.cohort_id for s in self.items.values() if s.role is role}


class FakeStaffTargetCatalog:
    def __init__(self, bootcamps: list[Bootcamp], cohorts: list[Cohort]) -> None:
        self.bootcamps = bootcamps
        self.cohorts = cohorts

    async def staffable_bootcamps(self) -> list[Bootcamp]:
        return list(self.bootcamps)

    async def staffable_cohorts(self) -> list[Cohort]:
        return list(self.cohorts)

    async def ensure_staffable(
        self, *, bootcamp_ids: Iterable[uuid.UUID], cohort_ids: Iterable[uuid.UUID]
    ) -> None:
        allowed = {b.id for b in self.bootcamps} | {c.id for c in self.cohorts}
        if not set(bootcamp_ids) | set(cohort_ids) <= allowed:
            raise BusinessRuleViolation("선택할 수 없는 담당입니다.", code="invalid_staff_target")

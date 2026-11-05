"""organization 인메모리 리포지토리와 담당 선택지 가짜 구현."""

import uuid
from collections.abc import Iterable
from dataclasses import replace

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.organization.domain.entities import Department, EmployeePosition
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

    async def list_all(self) -> list[Department]:
        return sorted(self.items.values(), key=lambda d: d.name)


class InMemoryEmployeePositionRepository:
    def __init__(self, *positions: EmployeePosition) -> None:
        self.items = {p.id: p for p in positions}

    async def add(self, position: EmployeePosition) -> None:
        self.items[position.id] = position

    async def save(self, position: EmployeePosition) -> None:
        self.items[position.id] = position

    async def get(self, entity_id: uuid.UUID) -> EmployeePosition | None:
        return self.items.get(entity_id)

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

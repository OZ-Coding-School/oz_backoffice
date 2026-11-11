"""mentoring 인메모리 리포지토리."""

import dataclasses
import uuid
from datetime import date

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.settings import MentoringBlockTime


class InMemoryCohortMentorRepository:
    def __init__(self, *assignments: CohortMentor) -> None:
        self.items = {a.id: dataclasses.replace(a) for a in assignments}

    async def add(self, assignment: CohortMentor) -> None:
        self.items[assignment.id] = dataclasses.replace(assignment)

    async def save(self, assignment: CohortMentor) -> None:
        self.items[assignment.id] = dataclasses.replace(assignment)

    async def get(self, assignment_id: uuid.UUID) -> CohortMentor | None:
        found = self.items.get(assignment_id)
        return dataclasses.replace(found) if found else None

    async def list_by_ids(self, assignment_ids: list[uuid.UUID]) -> list[CohortMentor]:
        return [dataclasses.replace(self.items[i]) for i in assignment_ids if i in self.items]

    async def find_active(
        self, mentor_id: uuid.UUID, cohort_id: uuid.UUID, period_type: MentoringPeriodType
    ) -> CohortMentor | None:
        for a in self.items.values():
            if (a.mentor_id, a.cohort_id, a.period_type, a.is_active) == (
                mentor_id,
                cohort_id,
                period_type,
                True,
            ):
                return dataclasses.replace(a)
        return None

    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]:
        return [
            dataclasses.replace(a)
            for a in self.items.values()
            if a.cohort_id == cohort_id and (include_inactive or a.is_active)
        ]

    async def list_by_mentor(
        self, mentor_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]:
        return [
            dataclasses.replace(a)
            for a in self.items.values()
            if a.mentor_id == mentor_id and (include_inactive or a.is_active)
        ]

    async def list_expired(self, today: date) -> list[CohortMentor]:
        return [
            dataclasses.replace(a)
            for a in self.items.values()
            if a.is_active and a.end_date is not None and a.end_date < today
        ]


class InMemoryUnavailablePeriodRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentorUnavailablePeriod] = {}

    async def add(self, period: MentorUnavailablePeriod) -> None:
        self.items[period.id] = dataclasses.replace(period)

    async def save(self, period: MentorUnavailablePeriod) -> None:
        self.items[period.id] = dataclasses.replace(period)

    async def get(self, period_id: uuid.UUID) -> MentorUnavailablePeriod | None:
        found = self.items.get(period_id)
        return dataclasses.replace(found) if found else None

    async def delete(self, period_id: uuid.UUID) -> None:
        self.items.pop(period_id, None)

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentorUnavailablePeriod]:
        found = [p for p in self.items.values() if p.mentor_id == mentor_id]
        return [dataclasses.replace(p) for p in sorted(found, key=lambda p: p.starts_at)]


class InMemoryBlockTimeRepository:
    def __init__(self, *blocks: MentoringBlockTime) -> None:
        self.items = {b.id: b for b in blocks}

    async def add(self, block: MentoringBlockTime) -> None:
        self.items[block.id] = block

    async def save(self, block: MentoringBlockTime) -> None:
        self.items[block.id] = block

    async def get(self, block_id: uuid.UUID) -> MentoringBlockTime | None:
        return self.items.get(block_id)

    async def delete(self, block_id: uuid.UUID) -> None:
        self.items.pop(block_id, None)

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringBlockTime]:
        return [b for b in self.items.values() if b.cohort_id == cohort_id]

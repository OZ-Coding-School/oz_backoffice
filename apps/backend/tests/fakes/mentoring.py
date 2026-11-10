"""mentoring 인메모리 리포지토리."""

import dataclasses
import uuid
from datetime import date

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import MentoringPeriodType


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

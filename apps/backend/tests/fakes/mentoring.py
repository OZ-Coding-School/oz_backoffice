"""mentoring 인메모리 리포지토리."""

import dataclasses
import uuid
from datetime import date

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.settings import CohortMentoringSettings, MentoringBlockTime
from app.contexts.mentoring.domain.team import MentoringTeam
from app.shared.errors import ConflictError


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


class InMemorySettingsRepository:
    def __init__(self, *items: CohortMentoringSettings) -> None:
        self.items = {s.cohort_id: s for s in items}

    async def get_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        return self.items.get(cohort_id)

    async def lock_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        return self.items.get(cohort_id)

    async def add(self, settings: CohortMentoringSettings) -> None:
        self.items[settings.cohort_id] = settings

    async def save(self, settings: CohortMentoringSettings) -> None:
        self.items[settings.cohort_id] = settings


class InMemoryTeamRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentoringTeam] = {}
        self.in_use: set[uuid.UUID] = set()  # 계좌·신청이 참조하는 팀

    def _copy(self, team: MentoringTeam) -> MentoringTeam:
        return dataclasses.replace(team, member_ids=list(team.member_ids))

    async def add(self, team: MentoringTeam) -> None:
        self.items[team.id] = self._copy(team)

    async def save(self, team: MentoringTeam) -> None:
        self.items[team.id] = self._copy(team)

    async def get(self, team_id: uuid.UUID) -> MentoringTeam | None:
        found = self.items.get(team_id)
        return self._copy(found) if found else None

    async def delete(self, team_id: uuid.UUID) -> None:
        if team_id in self.in_use:
            raise ConflictError("사용 중", code="team_in_use")
        self.items.pop(team_id, None)

    async def list_by_cohort(
        self, cohort_id: uuid.UUID, period_type: MentoringPeriodType | None
    ) -> list[MentoringTeam]:
        found = [
            t
            for t in self.items.values()
            if t.cohort_id == cohort_id and (period_type is None or t.period_type == period_type)
        ]
        return [self._copy(t) for t in sorted(found, key=lambda t: (t.period_type, t.team_number))]

    async def next_number(self, cohort_id: uuid.UUID, period_type: MentoringPeriodType) -> int:
        numbers = [
            t.team_number
            for t in self.items.values()
            if t.cohort_id == cohort_id and t.period_type == period_type
        ]
        return max(numbers, default=0) + 1

    async def team_of_students(
        self, student_ids: list[uuid.UUID], period_type: MentoringPeriodType
    ) -> dict[uuid.UUID, uuid.UUID]:
        return {
            s: t.id
            for t in self.items.values()
            if t.period_type == period_type
            for s in t.member_ids
            if s in student_ids
        }

    async def list_by_students(self, student_ids: list[uuid.UUID]) -> list[MentoringTeam]:
        return [self._copy(t) for t in self.items.values() if set(t.member_ids) & set(student_ids)]

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentoringTeam]:
        return [self._copy(t) for t in self.items.values() if t.mentor_id == mentor_id]

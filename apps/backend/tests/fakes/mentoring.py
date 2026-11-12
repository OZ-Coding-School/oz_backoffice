"""mentoring 인메모리 리포지토리."""

import dataclasses
import uuid
from datetime import date, datetime

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.contexts.mentoring.domain.request import MentoringRequest
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

    async def find_active(self, mentor_id: uuid.UUID, cohort_id: uuid.UUID) -> CohortMentor | None:
        for a in self.items.values():
            if (a.mentor_id, a.cohort_id, a.is_active) == (mentor_id, cohort_id, True):
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

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringTeam]:
        found = [t for t in self.items.values() if t.cohort_id == cohort_id]
        return [self._copy(t) for t in sorted(found, key=lambda t: t.team_number)]

    async def next_number(self, cohort_id: uuid.UUID) -> int:
        numbers = [t.team_number for t in self.items.values() if t.cohort_id == cohort_id]
        return max(numbers, default=0) + 1

    async def team_of_students(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        return {s: t.id for t in self.items.values() for s in t.member_ids if s in student_ids}

    async def list_by_students(self, student_ids: list[uuid.UUID]) -> list[MentoringTeam]:
        return [self._copy(t) for t in self.items.values() if set(t.member_ids) & set(student_ids)]

    async def list_memberships(self) -> list[tuple[uuid.UUID, uuid.UUID]]:
        return [(t.id, s) for t in self.items.values() for s in t.member_ids]

    async def remove_memberships(self, pairs: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
        for team_id, student_id in pairs:
            team = self.items.get(team_id)
            if team and student_id in team.member_ids:
                team.member_ids.remove(student_id)

    async def list_by_ids(self, team_ids: list[uuid.UUID]) -> list[MentoringTeam]:
        return [self._copy(self.items[i]) for i in team_ids if i in self.items]

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentoringTeam]:
        return [self._copy(t) for t in self.items.values() if t.mentor_id == mentor_id]


class InMemoryBalanceAccountRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, BalanceAccount] = {}

    async def add(self, account: BalanceAccount) -> None:
        self.items[account.id] = dataclasses.replace(account)

    async def save(self, account: BalanceAccount) -> None:
        self.items[account.id] = dataclasses.replace(account)

    async def get(self, account_id: uuid.UUID) -> BalanceAccount | None:
        found = self.items.get(account_id)
        return dataclasses.replace(found) if found else None

    async def lock_many(self, account_ids: list[uuid.UUID]) -> list[BalanceAccount]:
        return [dataclasses.replace(self.items[i]) for i in sorted(account_ids) if i in self.items]

    async def find_by_owners(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
    ) -> list[BalanceAccount]:
        return [
            dataclasses.replace(a)
            for a in self.items.values()
            if a.student_id in student_ids or a.team_id in team_ids
        ]

    async def list_student_accounts_with_remaining(self) -> list[BalanceAccount]:
        return [
            dataclasses.replace(a)
            for a in self.items.values()
            if a.student_id is not None and a.remaining_minutes > 0
        ]

    async def list_page(
        self,
        cohort_id: uuid.UUID,
        *,
        owner: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BalanceAccount], int]:
        found = [dataclasses.replace(a) for a in self.items.values()]
        return found[offset : offset + limit], len(found)


class InMemoryBalanceLedger:
    def __init__(self) -> None:
        self.entries: list[BalanceTransaction] = []

    async def add_many(self, entries: list[BalanceTransaction]) -> None:
        self.entries.extend(entries)

    async def list_by_account(
        self, account_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BalanceTransaction]:
        found = [
            e
            for e in reversed(self.entries)
            if e.account_id == account_id and (before is None or e.id < before)
        ]
        return found[:limit]


class InMemoryRequestRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentoringRequest] = {}

    def _copy(self, request: MentoringRequest) -> MentoringRequest:
        return dataclasses.replace(request, desired_times=list(request.desired_times))

    async def add(self, request: MentoringRequest) -> None:
        self.items[request.id] = self._copy(request)

    async def save(self, request: MentoringRequest) -> None:
        self.items[request.id] = self._copy(request)

    async def get(self, request_id: uuid.UUID) -> MentoringRequest | None:
        found = self.items.get(request_id)
        return self._copy(found) if found else None

    async def lock(self, request_id: uuid.UUID) -> MentoringRequest | None:
        return await self.get(request_id)

    async def get_many(self, request_ids: list[uuid.UUID]) -> dict[uuid.UUID, MentoringRequest]:
        return {i: self._copy(self.items[i]) for i in request_ids if i in self.items}

    async def count_pending(
        self, *, requester_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None
    ) -> int:
        pending = [r for r in self.items.values() if r.status is MentoringRequestStatus.PENDING]
        if team_id is not None:
            return sum(1 for r in pending if r.team_id == team_id)
        return sum(1 for r in pending if r.requester_id == requester_id and r.team_id is None)

    def _page(
        self, found: list[MentoringRequest], limit: int, offset: int
    ) -> tuple[list[MentoringRequest], int]:
        ordered = sorted(found, key=lambda r: r.id, reverse=True)
        return [self._copy(r) for r in ordered[offset : offset + limit]], len(ordered)

    async def list_for_participants(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        status: MentoringRequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        found = [
            r
            for r in self.items.values()
            if ((r.team_id is None and r.requester_id in student_ids) or r.team_id in team_ids)
            and (status is None or r.status is status)
        ]
        return self._page(found, limit, offset)

    async def list_for_mentor(
        self,
        mentor_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        found = [
            r
            for r in self.items.values()
            if r.mentor_id == mentor_id and (status is None or r.status is status)
        ]
        return self._page(found, limit, offset)

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        return self._page(list(self.items.values()), limit, offset)

    async def list_stale(self, now: datetime) -> list[MentoringRequest]:
        return [self._copy(r) for r in self.items.values() if r.is_stale(now)]

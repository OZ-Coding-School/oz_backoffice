"""mentoring 인메모리 리포지토리."""

import dataclasses
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.availability import Interval
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringRequestStatus, MentoringSessionStatus
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.session import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    MentoringSession,
    SessionQuery,
    SessionView,
)
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    PublicHoliday,
    PublicHolidaySync,
)
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.domain.transcript import TranscriptEntry
from app.shared.errors import ConflictError

if TYPE_CHECKING:
    from app.contexts.audit.application.recorder import AuditRecorder
    from app.contexts.mentoring.domain.artifact import MentoringArtifact
    from app.contexts.mentoring.domain.note import MentoringSessionNote
    from app.contexts.mentoring.domain.settlement import MentoringSettlement
    from app.core.clock import Clock
    from app.integrations.google.meet import MeetSpace


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
        self.cohort_of_student: dict[uuid.UUID, uuid.UUID] = {}  # list_pending(cohort_id=)용

    def _copy(self, request: MentoringRequest) -> MentoringRequest:
        return dataclasses.replace(request, desired_times=list(request.desired_times))

    async def add(self, request: MentoringRequest) -> None:
        self.items[request.id] = self._copy(request)

    async def chat_pairs(
        self, *, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID]
    ) -> set[tuple[uuid.UUID, uuid.UUID]]:
        pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for r in self.items.values():
            if r.team_id is not None and r.team_id in team_ids:
                pairs.add((r.mentor_id, r.team_id))
            elif r.team_id is None and r.requester_id in student_ids:
                pairs.add((r.mentor_id, r.requester_id))
        return pairs

    async def save(self, request: MentoringRequest) -> None:
        self.items[request.id] = self._copy(request)

    async def get(self, request_id: uuid.UUID) -> MentoringRequest | None:
        found = self.items.get(request_id)
        return self._copy(found) if found else None

    async def lock(self, request_id: uuid.UUID) -> MentoringRequest | None:
        return await self.get(request_id)

    async def get_many(self, request_ids: list[uuid.UUID]) -> dict[uuid.UUID, MentoringRequest]:
        return {i: self._copy(self.items[i]) for i in request_ids if i in self.items}

    async def list_pending(
        self,
        *,
        mentor_id: uuid.UUID | None = None,
        cohort_id: uuid.UUID | None = None,
        team_ids: list[uuid.UUID] | None = None,
        requester_ids: list[uuid.UUID] | None = None,
        solo: bool | None = None,
    ) -> list[MentoringRequest]:
        cohorts = self.cohort_of_student
        return [
            self._copy(r)
            for r in sorted(self.items.values(), key=lambda r: r.id)
            if r.status is MentoringRequestStatus.PENDING
            and (mentor_id is None or r.mentor_id == mentor_id)
            and (cohort_id is None or cohorts.get(r.requester_id) == cohort_id)
            and (team_ids is None or r.team_id in team_ids)
            and (requester_ids is None or r.requester_id in requester_ids)
            and (solo is None or (r.team_id is None) == solo)
        ]

    async def count_pending(
        self, *, requester_id: uuid.UUID | None = None, team_id: uuid.UUID | None = None
    ) -> int:
        pending = [r for r in self.items.values() if r.status is MentoringRequestStatus.PENDING]
        if team_id is not None:
            return sum(1 for r in pending if r.team_id == team_id)
        return sum(1 for r in pending if r.requester_id == requester_id and r.team_id is None)

    async def count_pending_by_requesters(
        self, requester_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        result: dict[uuid.UUID, int] = {}
        for r in self.items.values():
            if (
                r.status is MentoringRequestStatus.PENDING
                and r.team_id is None
                and r.requester_id in requester_ids
            ):
                result[r.requester_id] = result.get(r.requester_id, 0) + 1
        return result

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
        statuses: list[MentoringRequestStatus] | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        found = [
            r
            for r in self._of_participants(student_ids, team_ids)
            if not statuses or r.status in statuses
        ]
        return self._page(found, limit, offset)

    def _of_participants(
        self, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID]
    ) -> list[MentoringRequest]:
        return [
            r
            for r in self.items.values()
            if (r.team_id is None and r.requester_id in student_ids) or r.team_id in team_ids
        ]

    @staticmethod
    def _counts(found: list[MentoringRequest]) -> dict[MentoringRequestStatus, int]:
        counts = dict.fromkeys(MentoringRequestStatus, 0)
        for r in found:
            counts[r.status] += 1
        return counts

    async def count_statuses_for_participants(
        self, *, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID]
    ) -> dict[MentoringRequestStatus, int]:
        return self._counts(self._of_participants(student_ids, team_ids))

    async def count_statuses_for_mentor(
        self, mentor_id: uuid.UUID, *, cohort_id: uuid.UUID | None = None
    ) -> dict[MentoringRequestStatus, int]:
        # 기수는 보지 않는다 (인메모리 신청은 기수를 모른다)
        return self._counts([r for r in self.items.values() if r.mentor_id == mentor_id])

    async def list_for_mentor(
        self,
        mentor_id: uuid.UUID,
        *,
        statuses: list[MentoringRequestStatus] | None,
        limit: int,
        offset: int,
        cohort_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringRequest], int]:
        found = [
            r
            for r in self.items.values()
            if r.mentor_id == mentor_id and (not statuses or r.status in statuses)
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
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringRequest], int]:
        # 기수는 보지 않는다 (인메모리 신청은 기수를 모른다)
        found = [
            r
            for r in self.items.values()
            if (status is None or r.status is status)
            and (mentor_id is None or r.mentor_id == mentor_id)
            and (student_id is None or (r.requester_id == student_id and r.team_id is None))
            and (team_id is None or r.team_id == team_id)
        ]
        return self._page(found, limit, offset)

    async def list_stale(self, now: datetime) -> list[MentoringRequest]:
        return [self._copy(r) for r in self.items.values() if r.is_stale(now)]


class InMemorySessionRepository:
    """참여자 판정에 신청이 필요해 신청 리포지토리를 함께 받는다."""

    def __init__(self, requests: InMemoryRequestRepository) -> None:
        self.items: dict[uuid.UUID, MentoringSession] = {}
        self._requests = requests
        self.cohort_of_student: dict[uuid.UUID, uuid.UUID] = {}

    def _active(self) -> list[MentoringSession]:
        return [s for s in self.items.values() if s.status is not MentoringSessionStatus.CANCELED]

    async def add(self, session: MentoringSession) -> None:
        if any(
            s.mentor_id == session.mentor_id
            and s.starts_at < session.ends_at
            and session.starts_at < s.ends_at
            for s in self._active()
        ):
            raise ConflictError("멘토 일정 겹침", code="mentor_schedule_conflict")
        self.items[session.id] = dataclasses.replace(session)

    async def get(self, session_id: uuid.UUID) -> MentoringSession | None:
        found = self.items.get(session_id)
        return dataclasses.replace(found) if found else None

    async def get_many(self, session_ids: list[uuid.UUID]) -> dict[uuid.UUID, MentoringSession]:
        return {i: dataclasses.replace(self.items[i]) for i in session_ids if i in self.items}

    async def save(self, session: MentoringSession) -> None:
        self.items[session.id] = dataclasses.replace(session)

    async def list_upcoming(
        self,
        after: datetime,
        *,
        mentor_id: uuid.UUID | None = None,
        solo: bool | None = None,
    ) -> list[MentoringSession]:
        return [
            dataclasses.replace(s)
            for s in sorted(self.items.values(), key=lambda s: (s.starts_at, s.id))
            if s.status is MentoringSessionStatus.SCHEDULED
            and s.starts_at > after
            and (mentor_id is None or s.mentor_id == mentor_id)
            and (solo is None or (self._requests.items[s.request_id].team_id is None) == solo)
        ]

    async def lock(self, session_id: uuid.UUID) -> MentoringSession | None:
        return await self.get(session_id)

    async def get_by_space(self, space_name: str) -> MentoringSession | None:
        found = next((s for s in self.items.values() if s.google_space_name == space_name), None)
        return dataclasses.replace(found) if found else None

    async def list_needing_space(self, after: datetime) -> list[MentoringSession]:
        return [
            dataclasses.replace(s)
            for s in sorted(self.items.values(), key=lambda s: (s.starts_at, s.id))
            if s.needs_space and s.starts_at > after
        ]

    async def list_recent_with_space(
        self, since: datetime, until: datetime
    ) -> list[MentoringSession]:
        return [
            dataclasses.replace(s)
            for s in self._active()
            if s.google_space_name is not None and since <= s.ends_at <= until
        ]

    async def list_needing_close(self) -> list[MentoringSession]:
        return [dataclasses.replace(s) for s in self.items.values() if s.needs_space_closed]

    async def get_by_request(self, request_id: uuid.UUID) -> MentoringSession | None:
        found = next((s for s in self.items.values() if s.request_id == request_id), None)
        return dataclasses.replace(found) if found else None

    async def lock_by_request(self, request_id: uuid.UUID) -> MentoringSession | None:
        return await self.get_by_request(request_id)

    async def busy(
        self,
        mentor_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[Interval]:
        return sorted(
            (
                Interval(s.starts_at, s.ends_at)
                for s in self._active()
                if s.mentor_id == mentor_id
                and s.starts_at < end
                and start < s.ends_at
                and s.request_id != exclude_request_id
            ),
            key=lambda i: i.start,
        )

    def _matches(
        self, session: MentoringSession, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID]
    ) -> bool:
        request = self._requests.items[session.request_id]
        if request.team_id is not None:
            return request.team_id in team_ids
        return request.requester_id in student_ids

    async def count_for_pair(
        self, mentor_id: uuid.UUID, *, requester_id: uuid.UUID | None, team_id: uuid.UUID | None
    ) -> int:
        return sum(
            1
            for s in self._active()
            if s.mentor_id == mentor_id
            and self._matches(
                s, [requester_id] if requester_id else [], [team_id] if team_id else []
            )
        )

    async def has_participant_overlap(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        return any(
            s.starts_at < ends_at
            and starts_at < s.ends_at
            and self._matches(s, student_ids, team_ids)
            for s in self._active()
        )

    @staticmethod
    def _page(found: list[MentoringSession], q: SessionQuery) -> tuple[list[MentoringSession], int]:
        found = [
            s
            for s in found
            if (q.status is None or s.status is q.status)
            and (not q.statuses or s.status in q.statuses)
            and (q.starts_from is None or s.starts_at >= q.starts_from)
            and (q.starts_before is None or s.starts_at < q.starts_before)
            and (q.view is None or _in_view(s, q.view, q.now))
        ]
        found.sort(key=lambda s: (s.starts_at, s.id), reverse=not q.ascending)
        return found[q.offset : q.offset + q.limit], len(found)

    async def list_for_participants(
        self, *, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID], query: SessionQuery
    ) -> tuple[list[MentoringSession], int]:
        found = [s for s in self.items.values() if self._matches(s, student_ids, team_ids)]
        return self._page(found, query)

    async def list_for_mentor(
        self, mentor_id: uuid.UUID, query: SessionQuery
    ) -> tuple[list[MentoringSession], int]:
        return self._page([s for s in self.items.values() if s.mentor_id == mentor_id], query)

    @staticmethod
    def _status_counts(found: list[MentoringSession]) -> dict[MentoringSessionStatus, int]:
        counts = dict.fromkeys(MentoringSessionStatus, 0)
        for s in found:
            counts[s.status] += 1
        return counts

    async def count_statuses_for_participants(
        self, *, student_ids: list[uuid.UUID], team_ids: list[uuid.UUID]
    ) -> dict[MentoringSessionStatus, int]:
        return self._status_counts(
            [s for s in self.items.values() if self._matches(s, student_ids, team_ids)]
        )

    async def count_statuses_for_mentor(
        self, mentor_id: uuid.UUID, *, cohort_id: uuid.UUID | None = None
    ) -> dict[MentoringSessionStatus, int]:
        # 기수는 보지 않는다 (인메모리 세션은 기수를 모른다)
        return self._status_counts([s for s in self.items.values() if s.mentor_id == mentor_id])

    async def count_views_for_mentor(
        self, mentor_id: uuid.UUID, *, now: datetime, cohort_id: uuid.UUID | None = None
    ) -> dict[str, int]:
        mine = [s for s in self.items.values() if s.mentor_id == mentor_id]
        result = {"all": len(mine)}
        for view in SessionView:
            result[view.value] = sum(1 for s in mine if _in_view(s, view, now))
        return result

    async def list_settleable(
        self, cohort_id: uuid.UUID, *, before: datetime
    ) -> list[MentoringSession]:
        return [
            dataclasses.replace(s)
            for s in sorted(self.items.values(), key=lambda s: (s.starts_at, s.id))
            if self.cohort_of_student.get(self._requests.items[s.request_id].requester_id)
            == cohort_id
            and s.status in (MentoringSessionStatus.COMPLETED, MentoringSessionStatus.NO_SHOW)
            and s.recorded_at is not None
            and s.starts_at < before
        ]

    async def list_unrecorded(
        self,
        cohort_id: uuid.UUID,
        *,
        before: datetime,
        limit: int,
        offset: int,
        mentor_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringSession], int]:
        found = sorted(
            (
                s
                for s in self.items.values()
                if self.cohort_of_student.get(self._requests.items[s.request_id].requester_id)
                == cohort_id
                and s.status
                in (MentoringSessionStatus.SCHEDULED, MentoringSessionStatus.IN_PROGRESS)
                and s.starts_at < before
                and (mentor_id is None or s.mentor_id == mentor_id)
            ),
            key=lambda s: (s.starts_at, s.id),
        )
        return [dataclasses.replace(s) for s in found[offset : offset + limit]], len(found)

    async def count_by_requesters(
        self, requester_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, dict[MentoringSessionStatus, int]]:
        result: dict[uuid.UUID, dict[MentoringSessionStatus, int]] = {}
        for s in self.items.values():
            r = self._requests.items[s.request_id]
            if r.team_id is None and r.requester_id in requester_ids:
                by_status = result.setdefault(r.requester_id, {})
                by_status[s.status] = by_status.get(s.status, 0) + 1
        return result

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID | None,
        query: SessionQuery,
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringSession], int]:
        def matches(s: MentoringSession) -> bool:
            r = self._requests.items[s.request_id]
            return (
                self.cohort_of_student.get(r.requester_id) == cohort_id
                and (mentor_id is None or s.mentor_id == mentor_id)
                and (student_id is None or (r.requester_id == student_id and r.team_id is None))
                and (team_id is None or r.team_id == team_id)
            )

        found = [s for s in self.items.values() if matches(s)]
        return self._page(found, query)


class CleanupStores:
    """자동 정리(RequestCleanup)에 필요한 인메모리 저장소 묶음."""

    def __init__(self, audit: "AuditRecorder", clock: "Clock") -> None:
        from app.contexts.mentoring.application.request_cleanup import RequestCleanup

        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.cleanup = RequestCleanup(
            requests=self.requests,
            sessions=self.sessions,
            accounts=self.accounts,
            ledger=self.ledger,
            audit=audit,
            clock=clock,
        )

    async def pending(
        self,
        *,
        mentor_id: uuid.UUID,
        requester_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        at: datetime = datetime(2026, 11, 20, 5, tzinfo=UTC),
    ) -> MentoringRequest:
        """계좌(없으면 만들어 지급)에서 60분 보류한 대기 신청."""
        requester = requester_id or uuid.uuid4()
        found = await self.accounts.find_by_owners(
            student_ids=[] if team_id else [requester], team_ids=[team_id] if team_id else []
        )
        if found:
            account = self.accounts.items[found[0].id]
        else:
            account = BalanceAccount(
                student_id=None if team_id else requester,
                team_id=team_id,
                valid_from=date(2026, 11, 1),
                valid_until=date(2027, 4, 30),
            )
            account.grant(600, "지급", today=date(2026, 11, 1))
            await self.accounts.add(account)
            account = self.accounts.items[account.id]
        request = MentoringRequest(
            requester_id=requester,
            mentor_id=mentor_id,
            team_id=team_id,
            topic="주제",
            detail="내용",
            desired_times=[at],
            duration=60,
        )
        account.hold(60, request_id=request.id, reason="신청")
        await self.requests.add(request)
        return request

    def status(self, request: MentoringRequest) -> MentoringRequestStatus:
        return self.requests.items[request.id].status


class RecordingMeetScheduler:
    """승인 커밋 후 보낼 Meet 공간 생성 요청을 모은다 (TaskiqMeetScheduler 대신)."""

    def __init__(self) -> None:
        self.needed: list[uuid.UUID] = []

    async def space_needed(self, session_id: uuid.UUID) -> None:
        self.needed.append(session_id)


class FakeMeetClient:
    """만든 공간·막은 공간을 기록한다. fail_create/fail_restrict로 실패를 흉내 낸다."""

    def __init__(self) -> None:
        self.created: list[str] = []
        self.restricted: list[str] = []
        self.cohosts: list[tuple[str, str]] = []
        self.fail_create = 0  # 남은 실패 횟수
        self.fail_restrict = False
        self.fail_cohost = False

    async def create_space(self) -> "MeetSpace":
        from app.integrations.google.meet import MeetSpace, MeetUnavailableError

        if self.fail_create:
            self.fail_create -= 1
            raise MeetUnavailableError()
        name = f"spaces/s{len(self.created) + 1}"
        self.created.append(name)
        return MeetSpace(name=name, meeting_uri=f"https://meet.google.com/{name[7:]}")

    async def add_cohost(self, space_name: str, email: str) -> None:
        from app.integrations.google.meet import MeetUnavailableError

        if self.fail_cohost:
            raise MeetUnavailableError()
        self.cohosts.append((space_name, email))

    async def restrict_space(self, space_name: str) -> None:
        from app.integrations.google.meet import MeetUnavailableError

        if self.fail_restrict:
            raise MeetUnavailableError()
        self.restricted.append(space_name)


class InMemoryNoteRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentoringSessionNote] = {}

    async def get_by_session(self, session_id: uuid.UUID) -> "MentoringSessionNote | None":
        found = next((n for n in self.items.values() if n.session_id == session_id), None)
        return dataclasses.replace(found) if found else None

    async def add(self, note: "MentoringSessionNote") -> None:
        self.items[note.id] = dataclasses.replace(note)

    async def save(self, note: "MentoringSessionNote") -> None:
        self.items[note.id] = dataclasses.replace(note)


class InMemoryArtifactRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentoringArtifact] = {}

    async def add_if_absent(self, artifact: "MentoringArtifact") -> bool:
        if any(
            a.session_id == artifact.session_id and a.drive_file_id == artifact.drive_file_id
            for a in self.items.values()
        ):
            return False
        self.items[artifact.id] = dataclasses.replace(artifact)
        return True

    async def get(self, artifact_id: uuid.UUID) -> "MentoringArtifact | None":
        found = self.items.get(artifact_id)
        return dataclasses.replace(found) if found else None

    async def save(self, artifact: "MentoringArtifact") -> None:
        self.items[artifact.id] = dataclasses.replace(artifact)

    async def list_by_session(self, session_id: uuid.UUID) -> list["MentoringArtifact"]:
        return [dataclasses.replace(a) for a in self.items.values() if a.session_id == session_id]

    async def list_pending(self) -> list["MentoringArtifact"]:
        return [dataclasses.replace(a) for a in self.items.values() if a.needs_archive]


class InMemoryTranscriptEntryRepository:
    def __init__(self) -> None:
        self.items: list[TranscriptEntry] = []

    async def add_many(self, entries: list["TranscriptEntry"]) -> None:
        self.items.extend(dataclasses.replace(e) for e in entries)

    async def artifacts_with_entries(self, artifact_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        return {e.artifact_id for e in self.items if e.artifact_id in artifact_ids}

    async def list_by_artifact(self, artifact_id: uuid.UUID) -> list["TranscriptEntry"]:
        return sorted(
            (dataclasses.replace(e) for e in self.items if e.artifact_id == artifact_id),
            key=lambda e: e.sequence,
        )


class InMemorySettlementRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MentoringSettlement] = {}

    def _copy(self, s: "MentoringSettlement") -> "MentoringSettlement":
        return dataclasses.replace(s, items=[dataclasses.replace(i) for i in s.items])

    async def get(self, settlement_id: uuid.UUID) -> "MentoringSettlement | None":
        found = self.items.get(settlement_id)
        return self._copy(found) if found else None

    async def get_by_key(
        self, mentor_id: uuid.UUID, cohort_id: uuid.UUID, month: date
    ) -> "MentoringSettlement | None":
        found = next(
            (
                s
                for s in self.items.values()
                if (s.mentor_id, s.cohort_id, s.settlement_month) == (mentor_id, cohort_id, month)
            ),
            None,
        )
        return self._copy(found) if found else None

    async def save(self, settlement: "MentoringSettlement") -> None:
        taken = {
            i.session_id for s in self.items.values() if s.id != settlement.id for i in s.items
        }
        if taken & {i.session_id for i in settlement.items}:
            raise ConflictError("이미 정산된 세션", code="session_already_settled")
        self.items[settlement.id] = self._copy(settlement)

    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, month: date | None, with_items: bool = False
    ) -> list["MentoringSettlement"]:
        return [
            self._copy(s)
            for s in self.items.values()
            if s.cohort_id == cohort_id and (month is None or s.settlement_month == month)
        ]

    async def list_closed_by_mentor(self, mentor_id: uuid.UUID) -> list["MentoringSettlement"]:
        return sorted(
            (
                self._copy(s)
                for s in self.items.values()
                if s.mentor_id == mentor_id and s.is_closed
            ),
            key=lambda s: s.settlement_month,
            reverse=True,
        )

    async def settled_session_ids(
        self, session_ids: list[uuid.UUID], *, exclude_settlement_id: uuid.UUID | None
    ) -> set[uuid.UUID]:
        return {
            i.session_id
            for s in self.items.values()
            if s.id != exclude_settlement_id
            for i in s.items
            if i.session_id in session_ids
        }


def _in_view(session: MentoringSession, view: SessionView, now: datetime | None) -> bool:
    """`TortoiseMentoringSessionRepository._view`와 같은 탭 조건 (A77)."""
    if view is SessionView.PAST:
        return session.status in CLOSED_STATUSES
    assert now is not None
    if session.status not in OPEN_STATUSES:
        return False
    if view is SessionView.UPCOMING:
        return session.ends_at > now
    return session.starts_at <= now


class InMemoryPublicHolidayRepository:
    def __init__(self, *holidays: PublicHoliday) -> None:
        self.items = list(holidays)
        self.syncs: dict[int, PublicHolidaySync] = {}

    async def list_between(self, start: date, end: date) -> list[PublicHoliday]:
        found = [h for h in self.items if start <= h.holiday_date <= end]
        return sorted(found, key=lambda h: (h.holiday_date, h.name))

    async def replace_year(
        self, year: int, holidays: list[PublicHoliday], synced_at: datetime
    ) -> None:
        self.items = [h for h in self.items if h.holiday_date.year != year] + list(holidays)
        self.syncs[year] = PublicHolidaySync(
            year=year, synced_at=synced_at, holiday_count=len(holidays)
        )

    async def get_sync(self, year: int) -> PublicHolidaySync | None:
        return self.syncs.get(year)

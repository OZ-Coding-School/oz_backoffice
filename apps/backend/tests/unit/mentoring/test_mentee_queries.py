"""멘티 목록 (인메모리, A59)."""

import uuid
from collections.abc import Collection
from datetime import UTC, date, datetime, timedelta

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.mentoring.application.mentee_queries import MenteeQueries
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.team import MentoringTeam
from app.shared.ids import new_id
from tests.factories.academy import make_student
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryRequestRepository,
    InMemorySessionRepository,
    InMemoryTeamRepository,
)

pytestmark = pytest.mark.unit

T = datetime(2026, 11, 20, 5, tzinfo=UTC)
COHORT = new_id()


class FakeRoster:
    def __init__(self, students: list[Student]) -> None:
        self.students = students

    async def in_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        statuses: Collection[EnrollmentStatus] | None,
        name: str | None,
    ) -> list[Student]:
        return [
            s
            for s in sorted(self.students, key=lambda s: s.name)
            if s.cohort_id == cohort_id
            and (statuses is None or s.status in statuses)
            and (name or "") in s.name
        ]


class Harness:
    def __init__(self) -> None:
        self.students = [
            make_student(cohort_id=COHORT, name=name) for name in ("가수강", "나수강", "다수강")
        ]
        self.roster = FakeRoster(self.students)
        self.teams = InMemoryTeamRepository()
        self.accounts = InMemoryBalanceAccountRepository()
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.queries = MenteeQueries(
            roster=self.roster,
            teams=self.teams,
            accounts=self.accounts,
            requests=self.requests,
            sessions=self.sessions,
        )
        self.mentor_id = new_id()
        self.minute = 0

    async def request(
        self, student: Student, *, team_id: uuid.UUID | None = None
    ) -> MentoringRequest:
        self.minute += 1
        request = MentoringRequest(
            requester_id=student.id,
            team_id=team_id,
            mentor_id=self.mentor_id,
            topic="주제",
            detail="내용",
            desired_times=[T + timedelta(hours=self.minute)],
            duration=60,
        )
        await self.requests.add(request)
        return request

    async def session(
        self,
        student: Student,
        status: MentoringSessionStatus,
        *,
        team_id: uuid.UUID | None = None,
    ) -> None:
        request = await self.request(student, team_id=team_id)
        start, end = self.requests.items[request.id].approve(request.desired_times[0], now=T)
        session = MentoringSession(
            mentor_id=self.mentor_id,
            request_id=request.id,
            starts_at=start,
            ends_at=end,
            title="제목",
            topic="주제",
            status=status,
        )
        await self.sessions.add(session)


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_lists_roster_with_team_account_and_counts(h: Harness) -> None:
    ga, na, da = h.students
    team = MentoringTeam(cohort_id=COHORT, team_number=2, mentor_id=h.mentor_id, member_ids=[na.id])
    await h.teams.add(team)
    account = BalanceAccount(
        valid_from=date(2026, 11, 1), valid_until=date(2027, 1, 31), student_id=ga.id
    )
    account.grant(180, "기본 지급", today=date(2026, 11, 1))
    await h.accounts.add(account)
    await h.request(ga)  # 1:1 대기
    await h.request(ga)
    await h.request(na, team_id=team.id)  # 팀 신청은 세지 않는다
    await h.session(ga, MentoringSessionStatus.SCHEDULED)
    await h.session(ga, MentoringSessionStatus.IN_PROGRESS)
    await h.session(ga, MentoringSessionStatus.COMPLETED)
    await h.session(ga, MentoringSessionStatus.CANCELED)  # 취소·노쇼는 세지 않는다
    await h.session(na, MentoringSessionStatus.COMPLETED, team_id=team.id)

    items, total = await h.queries.list(COHORT, statuses=None, name=None, limit=50, offset=0)
    assert total == 3
    assert [m.student.name for m in items] == ["가수강", "나수강", "다수강"]
    first, second, third = items
    assert first.account is not None
    assert first.account.id == account.id
    assert (first.pending_requests, first.upcoming_sessions, first.completed_sessions) == (2, 2, 1)
    assert second.team is not None
    assert second.team.label == "2팀"
    assert (second.account, second.pending_requests, second.completed_sessions) == (None, 0, 0)
    assert (third.team, third.account, third.upcoming_sessions) == (None, None, 0)
    assert da.id == third.student.id


async def test_filters_and_pages_by_name_order(h: Harness) -> None:
    h.students[2].end(EnrollmentStatus.DROPPED, on=date(2026, 11, 15))
    enrolled, total = await h.queries.list(
        COHORT, statuses=[EnrollmentStatus.ENROLLED], name=None, limit=50, offset=0
    )
    assert (total, [m.student.name for m in enrolled]) == (2, ["가수강", "나수강"])
    named, _ = await h.queries.list(COHORT, statuses=None, name="다", limit=50, offset=0)
    assert [m.student.name for m in named] == ["다수강"]
    page, total = await h.queries.list(COHORT, statuses=None, name=None, limit=1, offset=1)
    assert (total, [m.student.name for m in page]) == (3, ["나수강"])
    assert await h.queries.list(COHORT, statuses=None, name=None, limit=10, offset=5) == ([], 3)

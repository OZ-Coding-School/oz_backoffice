"""멘토링 승인·반려·세션 조회 서비스 (인메모리 + 고정 시계, A42·A43)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.approval_service import MentoringApprovalService
from app.contexts.mentoring.application.session_service import MentoringSessionQueries
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringRequestStatus,
    MentoringSessionStatus,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import SessionQuery
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.shared.ids import new_id
from app.shared.time import KST
from tests.factories.identity import make_user
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemoryRequestRepository,
    InMemorySessionRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)
T = datetime(2026, 11, 16, 14, tzinfo=KST)


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, cohort_id: uuid.UUID, name: str) -> Student:
        student = Student(
            cohort_id=cohort_id,
            name=name,
            hrd_net_status=StudentStatus.TRAINING,
            enrolled_at=date(2026, 11, 1),
            user_id=new_id(),
        )
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


class Users:
    def __init__(self, *users: User) -> None:
        self.items = {u.id: u for u in users}

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
        return {i: self.items[i] for i in user_ids if i in self.items}


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        mentor_user = make_user(name="김멘토")
        other_user = make_user(name="박멘토")
        self.mentor = Mentor(
            user_id=mentor_user.id,
            nickname="코치킴",
            display_name_preference=DisplayNamePreference.NICKNAME,
        )
        self.other_mentor = Mentor(user_id=other_user.id)
        self.students = Students()
        self.student = self.students.add(self.cohort_id, "가수강")
        self.teams = InMemoryTeamRepository()
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.sessions.cohort_of_student = {self.student.id: self.cohort_id}
        self.clock = FixedClock(NOW)
        self.audit_logs = InMemoryAuditLogRepository()
        mentors = MentorQueries(InMemoryMentorRepository(self.mentor, self.other_mentor))
        self.service = MentoringApprovalService(
            requests=self.requests,
            sessions=self.sessions,
            accounts=self.accounts,
            ledger=self.ledger,
            teams=self.teams,
            students=self.students,
            mentors=mentors,
            users=Users(mentor_user, other_user),
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )
        self.queries = MentoringSessionQueries(
            sessions=self.sessions,
            requests=self.requests,
            teams=self.teams,
            students=self.students,
            mentors=mentors,
        )

    async def account(self, *, student_id: Any = None, team_id: Any = None) -> BalanceAccount:
        found = await self.accounts.find_by_owners(
            student_ids=[student_id] if student_id else [], team_ids=[team_id] if team_id else []
        )
        if found:
            return found[0]
        account = BalanceAccount(
            student_id=student_id,
            team_id=team_id,
            valid_from=date(2026, 11, 1),
            valid_until=date(2027, 4, 30),
        )
        account.grant(600, "지급", today=date(2026, 11, 11))
        await self.accounts.add(account)
        return account

    async def pending(
        self,
        *,
        student: Student | None = None,
        team: MentoringTeam | None = None,
        mentor: Mentor | None = None,
        times: list[datetime] | None = None,
    ) -> MentoringRequest:
        requester = student or self.student
        request = MentoringRequest(
            requester_id=requester.id,
            mentor_id=(mentor or self.mentor).id,
            team_id=team.id if team else None,
            topic="포트폴리오 리뷰",
            detail="봐 주세요",
            desired_times=times or [T, T + timedelta(hours=2)],
            duration=60,
        )
        account = await self.account(
            student_id=None if team else requester.id, team_id=team.id if team else None
        )
        stored = self.accounts.items[account.id]
        entry = stored.hold(60, request_id=request.id, reason="멘토링 신청")
        await self.ledger.add_many([entry])
        await self.requests.add(request)
        return request

    async def approve(self, request: MentoringRequest, at: datetime = T, **kw: Any) -> Any:
        user = kw.get("user", self.mentor.user_id)
        return await self.service.approve(user, request.id, at)


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_approve_creates_session_and_uses_time(h: Harness) -> None:
    request = await h.pending()
    approved, session = await h.approve(request, T + timedelta(hours=2))
    assert approved.status is MentoringRequestStatus.APPROVED
    assert (session.status, session.starts_at, session.ends_at - session.starts_at) == (
        MentoringSessionStatus.SCHEDULED,
        T + timedelta(hours=2),
        timedelta(minutes=60),
    )
    assert (session.title, session.topic) == ("가수강 · 코치킴 멘토링 1회차", "포트폴리오 리뷰")
    account = next(iter(h.accounts.items.values()))
    assert (account.held_minutes, account.used_minutes, account.remaining_minutes) == (0, 60, 540)
    assert h.ledger.entries[-1].type is MentoringBalanceTransactionType.USING
    assert [log.action for log in h.audit_logs.logs] == ["mentoring.request.approve"]

    second = await h.pending(times=[T + timedelta(days=1)])
    _, next_session = await h.approve(second, T + timedelta(days=1))
    assert next_session.title.endswith("2회차")


async def test_approve_rules(h: Harness) -> None:
    request = await h.pending()
    with pytest.raises(PermissionDeniedError) as other:
        await h.approve(request, user=h.other_mentor.user_id)
    assert other.value.code == "not_request_mentor"
    with pytest.raises(NotFoundError):
        await h.approve(request, user=new_id())  # 멘토 프로필 없음
    with pytest.raises(BusinessRuleViolation) as not_desired:
        await h.approve(request, T + timedelta(hours=1))
    assert not_desired.value.code == "not_desired_time"
    h.clock.set(T)
    with pytest.raises(BusinessRuleViolation) as passed:
        await h.approve(request, T)
    assert passed.value.code == "desired_time_passed"
    assert h.requests.items[request.id].status is MentoringRequestStatus.PENDING


async def test_mentor_and_participant_overlap(h: Harness) -> None:
    first = await h.pending()
    await h.approve(first)
    # 같은 멘토, 다른 수강생, 겹치는 시각 → 멘토 일정 겹침
    other_student = h.students.add(h.cohort_id, "나수강")
    clash = await h.pending(student=other_student, times=[T + timedelta(minutes=30)])
    with pytest.raises(ConflictError) as mentor_clash:
        await h.approve(clash, T + timedelta(minutes=30))
    assert mentor_clash.value.code == "mentor_schedule_conflict"
    # 다른 멘토, 같은 수강생, 겹치는 시각 → 신청자 일정 겹침
    elsewhere = await h.pending(mentor=h.other_mentor, times=[T])
    with pytest.raises(ConflictError) as mine:
        await h.service.approve(h.other_mentor.user_id, elsewhere.id, T)
    assert mine.value.code == "participant_schedule_conflict"
    account = await h.account(student_id=h.student.id)
    assert h.accounts.items[account.id].held_minutes == 60  # 실패한 승인은 반영되지 않는다


async def test_team_overlap_checks_members_one_on_one(h: Harness) -> None:
    member = h.students.add(h.cohort_id, "다수강")
    team = MentoringTeam(
        cohort_id=h.cohort_id,
        team_number=1,
        mentor_id=h.mentor.id,
        name="알파",
        member_ids=[h.student.id, member.id],
    )
    await h.teams.add(team)
    solo = await h.pending(student=member, mentor=h.other_mentor, times=[T])
    await h.service.approve(h.other_mentor.user_id, solo.id, T)

    team_request = await h.pending(student=h.student, team=team, times=[T, T + timedelta(hours=2)])
    with pytest.raises(ConflictError) as member_busy:  # 팀원의 1:1과 겹침
        await h.approve(team_request, T)
    assert member_busy.value.code == "participant_schedule_conflict"
    _, session = await h.approve(team_request, T + timedelta(hours=2))
    assert session.title == "알파 · 코치킴 멘토링 1회차"

    # 1:1 신청은 소속 팀 세션과도 겹치면 안 된다
    later = await h.pending(mentor=h.other_mentor, times=[T + timedelta(hours=2)])
    with pytest.raises(ConflictError):
        await h.service.approve(h.other_mentor.user_id, later.id, T + timedelta(hours=2))


async def test_reject_releases_hold(h: Harness) -> None:
    request = await h.pending()
    with pytest.raises(PermissionDeniedError):
        await h.service.reject(h.other_mentor.user_id, request.id, "안 됨")
    with pytest.raises(BusinessRuleViolation):
        await h.service.reject(h.mentor.user_id, request.id, " ")
    rejected = await h.service.reject(h.mentor.user_id, request.id, "일정이 맞지 않음")
    assert (rejected.status, rejected.reject_reason) == (
        MentoringRequestStatus.REJECTED,
        "일정이 맞지 않음",
    )
    account = next(iter(h.accounts.items.values()))
    assert (account.held_minutes, account.remaining_minutes) == (0, 600)
    assert h.ledger.entries[-1].type is MentoringBalanceTransactionType.RELEASE
    with pytest.raises(BusinessRuleViolation) as again:
        await h.approve(request)
    assert again.value.code == "request_not_pending"


async def test_session_queries(h: Harness) -> None:
    member = h.students.add(h.cohort_id, "다수강")
    team = MentoringTeam(
        cohort_id=h.cohort_id, team_number=1, mentor_id=h.mentor.id, member_ids=[member.id]
    )
    await h.teams.add(team)
    _, solo = await h.approve(await h.pending())
    team_request = await h.pending(student=member, team=team, times=[T + timedelta(hours=2)])
    _, team_session = await h.approve(team_request, T + timedelta(hours=2))

    student_user, member_user = h.student.user_id, member.user_id
    assert student_user is not None
    assert member_user is not None
    mine, total = await h.queries.list_mine(student_user, SessionQuery())
    assert (total, [s.id for s in mine]) == (1, [solo.id])
    theirs, _ = await h.queries.list_mine(member_user, SessionQuery())
    assert [s.id for s in theirs] == [team_session.id]
    _, mentor_total = await h.queries.list_for_mentor(h.mentor.user_id, SessionQuery())
    assert mentor_total == 2
    with pytest.raises(NotFoundError):
        await h.queries.list_for_mentor(new_id(), SessionQuery())

    assert (await h.queries.get_for_user(student_user, solo.id)).id == solo.id
    assert (await h.queries.get_for_user(h.mentor.user_id, team_session.id)).id == team_session.id
    for user, session_id in ((member_user, solo.id), (h.other_mentor.user_id, solo.id)):
        with pytest.raises(NotFoundError):  # 참여자·담당 멘토가 아니면 숨긴다
            await h.queries.get_for_user(user, session_id)
    assert (await h.queries.get_for_cohort(h.cohort_id, solo.id)).id == solo.id
    with pytest.raises(NotFoundError):
        await h.queries.get_for_cohort(new_id(), solo.id)
    _, cohort_total = await h.queries.list_by_cohort(
        h.cohort_id, mentor_id=None, query=SessionQuery()
    )
    assert cohort_total == 1  # 가짜 리포지토리에 기수를 등록한 수강생만

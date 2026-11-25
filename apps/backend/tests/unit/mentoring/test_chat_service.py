"""멘토링 채팅 서비스 (인메모리, A57·A74: 자격은 신청 이력)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.chat_service import ChatService, ChatTarget
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.chat import ChatEvent, ChatEventKind, ChatMessage
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringRequestStatus,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.ids import new_id
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryCohortMentorRepository,
    InMemoryRequestRepository,
    InMemoryTeamRepository,
)
from tests.fakes.mentoring_chat import InMemoryChatStore, RecordingChatEvents
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, cohort_id: uuid.UUID, **overrides: object) -> Student:
        values: dict[str, object] = {
            "cohort_id": cohort_id,
            "name": f"수강생{len(self.items) + 1}",
            "hrd_net_status": StudentStatus.TRAINING,
            "enrolled_at": date(2026, 11, 1),
            "user_id": new_id(),
        }
        values.update(overrides)
        student = Student(**values)  # type: ignore[arg-type]
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


def _assignment(mentor: Mentor, cohort_id: uuid.UUID) -> CohortMentor:
    return CohortMentor(
        cohort_id=cohort_id,
        mentor_id=mentor.id,
        start_date=date(2026, 11, 1),
        cost_settlement_policy=MentoringSettlementPolicy.ACTUAL_DURATION,
        pay_unit=PayUnit.HOURLY,
        pay_rate=30000,
    )


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.mentor = Mentor(user_id=new_id())
        self.other_mentor = Mentor(user_id=new_id())
        self.assignment = _assignment(self.mentor, self.cohort_id)
        self.assignments = InMemoryCohortMentorRepository(
            self.assignment, _assignment(self.other_mentor, self.cohort_id)
        )
        self.teams = InMemoryTeamRepository()
        self.requests = InMemoryRequestRepository()
        self.students = Students()
        self.student = self.students.add(self.cohort_id)
        self.clock = FixedClock(NOW)
        self.store = InMemoryChatStore({self.student.id: self.cohort_id})
        self.events = RecordingChatEvents()
        self.uow = FakeUnitOfWork()
        self.service = ChatService(
            threads=self.store.thread_repo,
            messages=self.store.message_repo,
            reads=self.store.read_repo,
            teams=self.teams,
            history=self.requests,
            students=self.students,
            mentors=MentorQueries(InMemoryMentorRepository(self.mentor, self.other_mentor)),
            events=self.events,
            uow=self.uow,
            clock=self.clock,
        )

    @property
    def student_user(self) -> uuid.UUID:
        assert self.student.user_id is not None
        return self.student.user_id

    def to_mentor(self, mentor: Mentor | None = None) -> ChatTarget:
        return ChatTarget(cohort_id=self.cohort_id, mentor_id=(mentor or self.mentor).id)

    async def team(self, *members: Student, mentor: Mentor | None = None) -> MentoringTeam:
        team = MentoringTeam(
            cohort_id=self.cohort_id,
            team_number=len(self.teams.items) + 1,
            mentor_id=(mentor or self.mentor).id,
            member_ids=[m.id for m in members],
        )
        await self.teams.add(team)
        self.store.cohort_of[team.id] = self.cohort_id
        return team

    async def applied(
        self,
        student: Student | None = None,
        *,
        mentor: Mentor | None = None,
        team: MentoringTeam | None = None,
        status: MentoringRequestStatus = MentoringRequestStatus.PENDING,
    ) -> None:
        """신청 이력을 남긴다 (A74: 상태 무관). 팀이면 팀 신청."""
        requester = student or self.student
        await self.requests.add(
            MentoringRequest(
                requester_id=requester.id,
                mentor_id=(mentor or self.mentor).id,
                team_id=team.id if team else None,
                topic="질문",
                detail="내용",
                desired_times=[NOW + timedelta(days=3)],
                duration=60,
                status=status,
            )
        )

    def tick(self, seconds: int = 1) -> None:
        self.clock.set(self.clock.now() + timedelta(seconds=seconds))


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_student_starts_direct_chat_and_mentor_replies(h: Harness) -> None:
    await h.applied(status=MentoringRequestStatus.REJECTED)  # 반려된 신청도 이력이다
    first = await h.service.start(h.student_user, h.to_mentor(), "  질문 있습니다 ")
    assert first.body == "질문 있습니다"
    assert len(h.store.threads) == 1
    thread_id = first.thread_id
    h.tick()
    again = await h.service.start(h.student_user, h.to_mentor(), "두 번째")
    assert again.thread_id == thread_id  # 같은 방

    mine, total = await h.service.list_threads(h.student_user, limit=20, offset=0)
    assert total == 1
    assert mine[0].unread_count == 0  # 내가 보낸 것
    assert mine[0].cohort_id == h.cohort_id
    assert mine[0].last_message is not None
    assert mine[0].last_message.id == again.id

    theirs, _ = await h.service.list_threads(h.mentor.account_id, limit=20, offset=0)
    assert [(v.thread.id, v.unread_count) for v in theirs] == [(thread_id, 2)]
    h.tick()
    reply = await h.service.send(h.mentor.account_id, thread_id, "답변입니다")
    assert (await h.service.get_thread(h.mentor.account_id, thread_id)).unread_count == 0
    assert (await h.service.get_thread(h.student_user, thread_id)).unread_count == 1
    assert h.store.threads[thread_id].last_message_at == reply.created_at

    # 멘토가 수강생을 골라 먼저 시작해도 같은 방
    h.tick()
    by_mentor = await h.service.start(
        h.mentor.account_id, ChatTarget(student_id=h.student.id), "확인했나요?"
    )
    assert by_mentor.thread_id == thread_id


async def test_start_rejects_targets_without_request_history(h: Harness) -> None:
    for user, target in [
        (h.student_user, h.to_mentor()),  # 배정은 있지만 신청 이력이 없다
        (h.student_user, ChatTarget(cohort_id=new_id(), mentor_id=h.mentor.id)),  # 다른 기수
        (h.student_user, ChatTarget(student_id=h.student.id)),  # 멘토가 아님
        (h.mentor.account_id, ChatTarget(student_id=h.student.id)),  # 멘토 쪽도 같은 기준
        (h.mentor.account_id, ChatTarget(student_id=new_id())),  # 없는 수강생
        (h.student_user, ChatTarget(team_id=new_id())),  # 없는 팀
    ]:
        with pytest.raises(NotFoundError) as error:
            await h.service.start(user, target, "안녕하세요")
        assert error.value.code == "chat_thread_not_found"
    with pytest.raises(BusinessRuleViolation) as missing:
        await h.service.start(h.student_user, ChatTarget(cohort_id=h.cohort_id), "안녕하세요")
    assert missing.value.code == "chat_target_required"
    await h.applied()
    with pytest.raises(BusinessRuleViolation) as empty:
        await h.service.start(h.student_user, h.to_mentor(), "   ")
    assert empty.value.code == "invalid_chat_message"
    assert h.store.threads == {}  # 검사에 실패하면 방을 만들지 않는다

    # 수강 상태·배정은 보지 않는다 (A74): 수강이 끝났어도 신청 이력이 있으면 대화한다
    ended = h.students.add(h.cohort_id, status=EnrollmentStatus.COMPLETED)
    assert ended.user_id is not None
    await h.applied(ended)
    assert (await h.service.start(ended.user_id, h.to_mentor(), "안녕하세요")).body == "안녕하세요"


async def test_team_chat_members_and_mentor_change(h: Harness) -> None:
    other = h.students.add(h.cohort_id)
    outsider = h.students.add(h.cohort_id)
    team = await h.team(h.student, other)
    await h.applied(team=team)
    await h.applied(outsider)  # 1:1 신청 이력은 팀 방 자격이 아니다
    first = await h.service.start(h.student_user, ChatTarget(team_id=team.id), "팀 질문")
    assert other.user_id is not None
    assert outsider.user_id is not None
    for user in (other.user_id, h.mentor.account_id):
        views, _ = await h.service.list_threads(user, limit=20, offset=0)
        assert [(v.thread.id, v.unread_count) for v in views] == [(first.thread_id, 1)]
    assert await h.service.list_threads(outsider.user_id, limit=20, offset=0) == ([], 0)
    with pytest.raises(NotFoundError):
        await h.service.send(outsider.user_id, first.thread_id, "끼어들기")
    with pytest.raises(NotFoundError):
        await h.service.start(outsider.user_id, ChatTarget(team_id=team.id), "끼어들기")

    # 담당 멘토가 바뀌어도 이전 방은 남는다(신청 이력). 새 멘토는 팀 신청이 있어야 새 방이 생긴다
    team.assign_mentor(h.other_mentor.id)
    await h.teams.save(team)
    assert [
        v.thread.id
        for v in (await h.service.list_threads(h.mentor.account_id, limit=20, offset=0))[0]
    ] == [first.thread_id]
    with pytest.raises(NotFoundError):
        await h.service.start(h.other_mentor.account_id, ChatTarget(team_id=team.id), "새 멘토")
    await h.applied(team=team, mentor=h.other_mentor)
    h.tick()
    second = await h.service.start(
        h.other_mentor.account_id, ChatTarget(team_id=team.id), "새 멘토"
    )
    assert second.thread_id != first.thread_id
    views, _ = await h.service.list_threads(h.student_user, limit=20, offset=0)
    assert {v.thread.id for v in views} == {first.thread_id, second.thread_id}

    # 팀에서 빠지면 그 팀 방은 보이지 않는다 (참여자는 지금 팀원)
    team.remove_member(other.id)
    await h.teams.save(team)
    assert await h.service.list_threads(other.user_id, limit=20, offset=0) == ([], 0)


async def test_threads_stay_after_enrollment_or_assignment_ends(h: Harness) -> None:
    """A74: 자격은 신청 이력만 본다. 수강이 끝나거나 배정이 끝나도 방은 그대로다."""
    await h.applied()
    sent = await h.service.start(h.student_user, h.to_mentor(), "질문")
    h.student.end(EnrollmentStatus.COMPLETED, on=date(2026, 11, 15))
    h.assignment.deactivate(CohortMentorDeactivationReason.MANUAL, now=NOW)
    await h.assignments.save(h.assignment)
    for user in (h.student_user, h.mentor.account_id):
        assert (await h.service.list_threads(user, limit=20, offset=0))[1] == 1
    h.tick()
    assert (await h.service.send(h.mentor.account_id, sent.thread_id, "답변")).body == "답변"
    staff, total = await h.service.list_by_cohort(h.cohort_id, mentor_id=None, limit=20, offset=0)
    assert total == 1
    assert staff[0].unread_count == 0


async def test_messages_cursor_delete_and_read(h: Harness) -> None:
    await h.applied()
    await h.applied(mentor=h.other_mentor)
    sent = []
    for i in range(5):
        h.tick()
        sent.append(await h.service.start(h.student_user, h.to_mentor(), f"메시지 {i}"))
    thread_id = sent[0].thread_id
    page = await h.service.list_messages(h.mentor.account_id, thread_id, before=None, limit=2)
    assert [m.body for m in page] == ["메시지 4", "메시지 3"]
    older = await h.service.list_messages(h.mentor.account_id, thread_id, before=page[-1].id)
    assert [m.body for m in older] == ["메시지 2", "메시지 1", "메시지 0"]

    with pytest.raises(PermissionDeniedError):
        await h.service.delete_message(h.mentor.account_id, thread_id, sent[4].id)
    deleted = await h.service.delete_message(h.student_user, thread_id, sent[4].id)
    assert deleted.is_deleted
    stored = await h.service.list_messages(h.mentor.account_id, thread_id, before=None, limit=1)
    assert stored[0].id == sent[4].id
    assert stored[0].body is None
    assert (await h.service.get_thread(h.mentor.account_id, thread_id)).unread_count == 4

    view = await h.service.mark_read(h.mentor.account_id, thread_id, sent[2].id)
    assert view.unread_count == 1
    view = await h.service.mark_read(h.mentor.account_id, thread_id, sent[0].id)  # 뒤로 가지 않음
    assert view.unread_count == 1
    other = await h.service.start(h.student_user, h.to_mentor(h.other_mentor), "다른 방")
    for call in (
        h.service.mark_read(h.mentor.account_id, thread_id, other.id),
        h.service.delete_message(h.student_user, thread_id, other.id),
    ):
        with pytest.raises(NotFoundError) as error:
            await call
        assert error.value.code == "chat_message_not_found"


async def test_staff_reads_threads_in_cohort(h: Harness) -> None:
    await h.applied()
    sent = await h.service.start(h.student_user, h.to_mentor(), "질문")
    view = await h.service.get_for_cohort(h.cohort_id, sent.thread_id)
    assert view.last_message is not None
    assert view.last_message.id == sent.id
    messages = await h.service.messages_for_cohort(h.cohort_id, sent.thread_id, before=None)
    assert [m.id for m in messages] == [sent.id]
    for call in (
        h.service.get_for_cohort(new_id(), sent.thread_id),
        h.service.messages_for_cohort(new_id(), sent.thread_id, before=None),
        h.service.get_for_cohort(h.cohort_id, new_id()),
    ):
        with pytest.raises(NotFoundError):
            await call
    filtered, total = await h.service.list_by_cohort(
        h.cohort_id, mentor_id=h.other_mentor.id, limit=20, offset=0
    )
    assert (filtered, total) == ([], 0)
    by_student, _ = await h.service.list_by_cohort(
        h.cohort_id, mentor_id=None, limit=20, offset=0, student_id=h.student.id
    )
    assert [v.thread.id for v in by_student] == [sent.thread_id]
    assert await h.service.list_by_cohort(
        h.cohort_id, mentor_id=None, limit=20, offset=0, team_id=new_id()
    ) == ([], 0)


async def test_events_go_to_participants_after_commit(h: Harness) -> None:
    other = h.students.add(h.cohort_id)
    team = await h.team(h.student, other)
    await h.applied(team=team)
    assert other.user_id is not None
    sent = await h.service.start(h.student_user, ChatTarget(team_id=team.id), "팀 질문")
    everyone = {h.student_user, other.user_id, h.mentor.account_id}
    assert h.events.sent == [
        (everyone, ChatEvent(ChatEventKind.MESSAGE, sent.thread_id, sent.id)),
    ]
    h.events.sent.clear()
    await h.service.mark_read(other.user_id, sent.thread_id, sent.id)
    assert h.events.sent == [({other.user_id}, ChatEvent(ChatEventKind.READ, sent.thread_id))]
    h.events.sent.clear()
    await h.service.mark_read(other.user_id, sent.thread_id, sent.id)  # 그대로면 알리지 않음
    await h.service.delete_message(h.student_user, sent.thread_id, sent.id)
    assert h.events.sent == [
        (everyone, ChatEvent(ChatEventKind.MESSAGE_DELETED, sent.thread_id, sent.id)),
    ]

    # 알림이 실패해도 보내기는 성공 (이미 커밋됨)
    h.events.fail = True
    h.tick()
    kept = await h.service.send(h.mentor.account_id, sent.thread_id, "답변")
    assert kept.id in h.store.messages


async def test_post_notice_creates_thread_and_notifies(h: Harness) -> None:
    await h.applied()  # 안내는 신청과 함께 남는다
    async with h.uow:
        notice = await h.service.post_notice(
            mentor_id=h.mentor.id, student_id=h.student.id, team_id=None, body="[멘토링 신청] 주제"
        )
        assert h.events.sent == []  # 커밋 뒤에 알린다
    assert notice is not None
    assert notice.is_system
    assert h.events.sent == [
        (
            {h.student_user, h.mentor.account_id},
            ChatEvent(ChatEventKind.MESSAGE, notice.thread_id, notice.id),
        )
    ]
    view = await h.service.get_thread(h.student_user, notice.thread_id)
    assert view.unread_count == 1  # 안내도 안 읽음에 들어간다
    assert (await h.service.get_message(h.mentor.account_id, notice.thread_id, notice.id)).body == (
        "[멘토링 신청] 주제"
    )

    # 자격(신청 이력)이 없는 방에도 남기되(운영진 열람) 알리지 않는다
    h.events.sent.clear()
    hidden = await h.service.post_notice(
        mentor_id=h.other_mentor.id, student_id=h.student.id, team_id=None, body="[안내]"
    )
    assert hidden is not None
    assert h.events.sent == []


async def test_post_notice_failure_is_swallowed(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(_: ChatMessage) -> None:
        raise RuntimeError("db")

    monkeypatch.setattr(h.store.message_repo, "add", broken)
    notice = await h.service.post_notice(
        mentor_id=h.mentor.id, student_id=h.student.id, team_id=None, body="안내"
    )
    assert notice is None
    assert h.events.sent == []

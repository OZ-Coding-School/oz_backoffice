"""멘토링 채팅 (decisions M23·A57, P15-1).

참여 자격 (양쪽 같은 기준, 없으면 목록에서 빠지고 단건은 404):
- 1:1: 수강 등록이 수강 중이고 그 기수에 그 멘토의 활성 배정이 있다. 참여자는 그 수강생과 멘토.
- 팀: 팀의 현재 담당 멘토가 방의 멘토이고 그 기수에 활성 배정이 있다. 참여자는 현재 팀원과 멘토.
  담당 멘토가 바뀌면 새 멘토와 새 방이 생긴다.
방은 처음 메시지를 보낼 때 만든다(수강생·멘토 누구나 먼저 시작).
보내면 보낸 사람의 읽음 위치도 그 메시지로 옮긴다.
운영진(기수 범위)은 방과 메시지를 열람만 한다.
실시간 알림(A58): 커밋 뒤 참여자 각자에게 새 메시지·삭제를, 읽은 사람에게 읽음을 알린다. 알림 실패는
기록만 하고 요청은 성공으로 둔다(놓친 알림은 다시 조회로 맞춘다).
안내 메시지(P15-2): 호출한 트랜잭션 안의 savepoint에 남겨 실패해도 원래 처리를 되돌리지 않는다.
"""

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.chat import (
    MESSAGE_MAX_LENGTH,
    ChatEvent,
    ChatEventKind,
    ChatMessage,
    ChatRead,
    ChatThread,
    clean_message,
)
from app.contexts.mentoring.domain.repositories import (
    ChatMessageRepository,
    ChatReadRepository,
    ChatThreadRepository,
    CohortMentorRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import Clock
from app.core.uow import UnitOfWork, after_commit
from app.shared.errors import BusinessRuleViolation, NotFoundError

logger = logging.getLogger(__name__)

MESSAGE_PAGE_DEFAULT = 50


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...
    async def of_user(self, user_id: uuid.UUID) -> list[Student]: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


class ChatEventPublisher(Protocol):
    """mentoring `RedisChatEvents`."""

    async def publish(self, user_ids: Iterable[uuid.UUID], event: ChatEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class ChatTarget:
    """처음 보낼 상대 (하나만).

    팀은 `team_id`, 수강생→멘토는 `cohort_id`·`mentor_id`, 멘토→수강생은 `student_id`.
    """

    team_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ThreadView:
    thread: ChatThread
    cohort_id: uuid.UUID
    last_message: ChatMessage | None
    unread_count: int = 0


@dataclass(frozen=True, slots=True)
class _Viewer:
    user_id: uuid.UUID
    registrations: list[Student]
    mentor: Mentor | None

    def is_mentor_of(self, thread: ChatThread) -> bool:
        return self.mentor is not None and self.mentor.id == thread.mentor_id


@dataclass(frozen=True, slots=True)
class _Scope:
    """자격 판정에 필요한 방들의 수강 등록·팀·활성 배정."""

    students: dict[uuid.UUID, Student]
    teams: dict[uuid.UUID, MentoringTeam]
    active: set[tuple[uuid.UUID, uuid.UUID]]  # (멘토, 기수)

    def cohort_of(self, thread: ChatThread) -> uuid.UUID | None:
        if thread.team_id is not None:
            team = self.teams.get(thread.team_id)
            return team.cohort_id if team else None
        student = self.students.get(thread.student_id) if thread.student_id else None
        return student.cohort_id if student else None

    def open(self, thread: ChatThread) -> bool:
        """방이 아직 쓰이는가 (참여자와 무관한 조건)."""
        cohort_id = self.cohort_of(thread)
        if cohort_id is None or (thread.mentor_id, cohort_id) not in self.active:
            return False
        if thread.team_id is not None:
            return self.teams[thread.team_id].mentor_id == thread.mentor_id
        return thread.student_id is not None and _enrolled(self.students[thread.student_id])


def _enrolled(student: Student) -> bool:
    return student.is_enrolled and not student.is_removed_in_source


def _thread_not_found() -> NotFoundError:
    return NotFoundError("채팅방을 찾을 수 없습니다.", code="chat_thread_not_found")


def _message_not_found() -> NotFoundError:
    return NotFoundError("메시지를 찾을 수 없습니다.", code="chat_message_not_found")


class ChatService:
    def __init__(
        self,
        *,
        threads: ChatThreadRepository,
        messages: ChatMessageRepository,
        reads: ChatReadRepository,
        teams: MentoringTeamRepository,
        assignments: CohortMentorRepository,
        students: StudentLookup,
        mentors: MentorLookup,
        events: ChatEventPublisher,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._events = events
        self._threads = threads
        self._messages = messages
        self._reads = reads
        self._teams = teams
        self._assignments = assignments
        self._students = students
        self._mentors = mentors
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 참여자 조회
    async def list_threads(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[ThreadView], int]:
        """참여 중인 방 (마지막 메시지 최신순, 자격이 없어진 방은 빠짐)."""
        viewer = await self._viewer(user_id)
        registrations = [s.id for s in viewer.registrations]
        teams = await self._teams.list_by_students(registrations)
        candidates = await self._threads.list_for(
            student_ids=registrations,
            team_ids=[t.id for t in teams],
            mentor_id=viewer.mentor.id if viewer.mentor else None,
        )
        scope = await self._scope(candidates)
        visible = [t for t in candidates if self._participates(viewer, scope, t)]
        page = visible[offset : offset + limit]
        return await self._views(page, scope, user_id=user_id), len(visible)

    async def get_thread(self, user_id: uuid.UUID, thread_id: uuid.UUID) -> ThreadView:
        thread, scope = await self._accessible(user_id, thread_id)
        return (await self._views([thread], scope, user_id=user_id))[0]

    async def list_messages(
        self,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        *,
        before: uuid.UUID | None,
        limit: int = MESSAGE_PAGE_DEFAULT,
    ) -> list[ChatMessage]:
        """최신부터 limit개 (before가 있으면 그보다 앞선 것)."""
        await self._accessible(user_id, thread_id)
        return await self._messages.list_before(thread_id, before=before, limit=limit)

    # ------------------------------------------------------------------ 보내기·지우기·읽기
    async def send(self, user_id: uuid.UUID, thread_id: uuid.UUID, body: str) -> ChatMessage:
        thread, scope = await self._accessible(user_id, thread_id)
        message = ChatMessage.write(thread.id, user_id, body, now=self._clock.now())
        async with self._uow:
            await self._store(message)
            self._notify_after_commit(thread, scope, ChatEventKind.MESSAGE, message.id)
        return message

    async def start(self, user_id: uuid.UUID, target: ChatTarget, body: str) -> ChatMessage:
        """상대를 골라 보낸다. 방이 없으면 만든다."""
        text = clean_message(body)  # 방을 만들기 전에 검사
        spec = await self._resolve(await self._viewer(user_id), target)
        async with self._uow:
            thread = await self._threads.ensure(spec)
            message = ChatMessage.write(thread.id, user_id, text, now=self._clock.now())
            await self._store(message)
            scope = await self._scope([thread])
            self._notify_after_commit(thread, scope, ChatEventKind.MESSAGE, message.id)
        return message

    async def delete_message(
        self, user_id: uuid.UUID, thread_id: uuid.UUID, message_id: uuid.UUID
    ) -> ChatMessage:
        thread, scope = await self._accessible(user_id, thread_id)
        message = await self._message_in(thread_id, message_id)
        async with self._uow:
            if message.delete(user_id, now=self._clock.now()):
                await self._messages.save(message)
                self._notify_after_commit(thread, scope, ChatEventKind.MESSAGE_DELETED, message.id)
        return message

    async def mark_read(
        self, user_id: uuid.UUID, thread_id: uuid.UUID, message_id: uuid.UUID
    ) -> ThreadView:
        """본 마지막 메시지까지 읽음 (앞으로만)."""
        thread, scope = await self._accessible(user_id, thread_id)
        await self._message_in(thread_id, message_id)
        read = await self._reads.get(thread_id, user_id) or ChatRead(
            thread_id=thread_id, user_id=user_id
        )
        if read.advance(message_id, now=self._clock.now()):
            async with self._uow:
                await self._reads.save(read)
                event = ChatEvent(kind=ChatEventKind.READ, thread_id=thread_id)
                self._uow.on_commit(lambda: self._publish([user_id], event))
        return (await self._views([thread], scope, user_id=user_id))[0]

    async def get_message(
        self, user_id: uuid.UUID, thread_id: uuid.UUID, message_id: uuid.UUID
    ) -> ChatMessage:
        """실시간 알림을 받은 사람이 메시지를 다시 읽는다 (자격이 없으면 404)."""
        await self._accessible(user_id, thread_id)
        return await self._message_in(thread_id, message_id)

    # ------------------------------------------------------------------ 안내 메시지
    async def post_notice(
        self,
        *,
        mentor_id: uuid.UUID,
        student_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        body: str,
    ) -> ChatMessage | None:
        """그 방(없으면 만듦)에 안내 메시지를 남긴다. 호출한 트랜잭션 안에서 savepoint로 쓰고
        실패하면 기록만 하고 None (원래 처리는 그대로). 알림은 커밋 뒤."""
        spec = ChatThread(
            mentor_id=mentor_id, student_id=None if team_id else student_id, team_id=team_id
        )
        text = body.strip()[:MESSAGE_MAX_LENGTH]
        try:
            async with self._uow.savepoint():
                thread = await self._threads.ensure(spec)
                message = ChatMessage.write(thread.id, None, text, now=self._clock.now())
                await self._store(message)
        except Exception:
            logger.exception("채팅 안내를 남기지 못했습니다 (멘토 %s)", mentor_id)
            return None
        scope = await self._scope([thread])
        event = ChatEvent(kind=ChatEventKind.MESSAGE, thread_id=thread.id, message_id=message.id)
        users = await self._participant_users(thread, scope)
        await after_commit(lambda: self._publish(users, event))
        return message

    # ------------------------------------------------------------------ 운영진 열람
    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[ThreadView], int]:
        threads, total = await self._threads.list_by_cohort(
            cohort_id,
            mentor_id=mentor_id,
            limit=limit,
            offset=offset,
            student_id=student_id,
            team_id=team_id,
        )
        return await self._views(threads, await self._scope(threads), user_id=None), total

    async def get_for_cohort(self, cohort_id: uuid.UUID, thread_id: uuid.UUID) -> ThreadView:
        thread, scope = await self._in_cohort(cohort_id, thread_id)
        return (await self._views([thread], scope, user_id=None))[0]

    async def messages_for_cohort(
        self,
        cohort_id: uuid.UUID,
        thread_id: uuid.UUID,
        *,
        before: uuid.UUID | None,
        limit: int = MESSAGE_PAGE_DEFAULT,
    ) -> list[ChatMessage]:
        await self._in_cohort(cohort_id, thread_id)
        return await self._messages.list_before(thread_id, before=before, limit=limit)

    # ------------------------------------------------------------------ 내부
    async def _store(self, message: ChatMessage) -> None:
        """메시지를 저장하고 방 정렬 시각과 보낸 사람의 읽음 위치를 옮긴다 (트랜잭션 안)."""
        await self._messages.add(message)
        await self._threads.touch(message.thread_id, message.created_at)
        if message.sender_id is not None:
            read = ChatRead(thread_id=message.thread_id, user_id=message.sender_id)
            read.advance(message.id, now=message.created_at)
            await self._reads.save(read)

    def _notify_after_commit(
        self,
        thread: ChatThread,
        scope: _Scope,
        kind: ChatEventKind,
        message_id: uuid.UUID,
    ) -> None:
        event = ChatEvent(kind=kind, thread_id=thread.id, message_id=message_id)

        async def notify() -> None:
            await self._publish(await self._participant_users(thread, scope), event)

        self._uow.on_commit(notify)

    async def _participant_users(self, thread: ChatThread, scope: _Scope) -> list[uuid.UUID]:
        """지금 그 방을 볼 수 있는 회원 (자격이 없는 방이면 없음)."""
        if not scope.open(thread):
            return []
        mentor = await self._mentors.get(thread.mentor_id)
        users = [mentor.user_id] if mentor else []
        if thread.team_id is not None:
            members = await self._students.get_many(scope.teams[thread.team_id].member_ids)
            users += [s.user_id for s in members.values() if s.user_id]
        elif thread.student_id is not None:
            student = scope.students[thread.student_id]
            users += [student.user_id] if student.user_id else []
        return users

    async def _publish(self, user_ids: list[uuid.UUID], event: ChatEvent) -> None:
        if not user_ids:
            return
        try:
            await self._events.publish(user_ids, event)
        except Exception:  # 이미 커밋됐다. 놓친 알림은 다시 조회로 맞춘다 (A58)
            logger.warning("채팅 실시간 알림 실패 (방 %s)", event.thread_id, exc_info=True)

    async def _viewer(self, user_id: uuid.UUID) -> _Viewer:
        return _Viewer(
            user_id=user_id,
            registrations=await self._students.of_user(user_id),
            mentor=await self._mentors.get_by_user(user_id),
        )

    async def _scope(self, threads: list[ChatThread]) -> _Scope:
        students = await self._students.get_many(
            list({t.student_id for t in threads if t.student_id})
        )
        teams = {
            t.id: t
            for t in await self._teams.list_by_ids(list({t.team_id for t in threads if t.team_id}))
        }
        active: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for mentor_id in {t.mentor_id for t in threads}:
            for a in await self._assignments.list_by_mentor(mentor_id, include_inactive=False):
                active.add((a.mentor_id, a.cohort_id))
        return _Scope(students=students, teams=teams, active=active)

    @staticmethod
    def _participates(viewer: _Viewer, scope: _Scope, thread: ChatThread) -> bool:
        if not scope.open(thread):
            return False
        if viewer.is_mentor_of(thread):
            return True
        mine = {s.id for s in viewer.registrations}
        if thread.team_id is not None:
            return any(m in mine for m in scope.teams[thread.team_id].member_ids)
        return thread.student_id in mine

    async def _accessible(
        self, user_id: uuid.UUID, thread_id: uuid.UUID
    ) -> tuple[ChatThread, _Scope]:
        thread = await self._threads.get(thread_id)
        if thread is None:
            raise _thread_not_found()
        scope = await self._scope([thread])
        if not self._participates(await self._viewer(user_id), scope, thread):
            raise _thread_not_found()
        return thread, scope

    async def _in_cohort(
        self, cohort_id: uuid.UUID, thread_id: uuid.UUID
    ) -> tuple[ChatThread, _Scope]:
        thread = await self._threads.get(thread_id)
        if thread is None:
            raise _thread_not_found()
        scope = await self._scope([thread])
        if scope.cohort_of(thread) != cohort_id:
            raise _thread_not_found()
        return thread, scope

    async def _message_in(self, thread_id: uuid.UUID, message_id: uuid.UUID) -> ChatMessage:
        message = await self._messages.get(message_id)
        if message is None or message.thread_id != thread_id:
            raise _message_not_found()
        return message

    async def _resolve(self, viewer: _Viewer, target: ChatTarget) -> ChatThread:
        """상대 → 만들 방 (자격 검사 포함, 없거나 자격이 없으면 404)."""
        if target.team_id is not None:
            team = await self._teams.get(target.team_id)
            if team is None:
                raise _thread_not_found()
            spec = ChatThread(mentor_id=team.mentor_id, team_id=team.id)
        elif target.student_id is not None:
            if viewer.mentor is None:
                raise _thread_not_found()
            spec = ChatThread(mentor_id=viewer.mentor.id, student_id=target.student_id)
        elif target.cohort_id is not None and target.mentor_id is not None:
            found = next((s for s in viewer.registrations if s.cohort_id == target.cohort_id), None)
            if found is None:
                raise _thread_not_found()
            spec = ChatThread(mentor_id=target.mentor_id, student_id=found.id)
        else:
            raise BusinessRuleViolation(
                "보낼 상대(팀, 기수와 멘토, 수강생 중 하나)를 골라 주세요.",
                code="chat_target_required",
            )
        if not self._participates(viewer, await self._scope([spec]), spec):
            raise _thread_not_found()
        return spec

    async def _views(
        self, threads: list[ChatThread], scope: _Scope, *, user_id: uuid.UUID | None
    ) -> list[ThreadView]:
        ids = [t.id for t in threads]
        last = await self._threads.last_messages(ids)
        unread = await self._threads.unread_counts(user_id, ids) if user_id else {}
        views = []
        for t in threads:
            cohort_id = scope.cohort_of(t)
            if cohort_id is None:  # 수강 등록·팀이 지워진 방 (참조 제약으로 생기지 않음)
                continue
            views.append(ThreadView(t, cohort_id, last.get(t.id), unread.get(t.id, 0)))
        return views

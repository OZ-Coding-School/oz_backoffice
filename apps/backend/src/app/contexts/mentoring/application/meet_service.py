"""멘토링 세션의 Google Meet 공간 (decisions A46·A48, P12-1).

- 승인 커밋 후 작업이 공간을 만든다(`ensure_space`, 작업이 재시도). 만들자마자 담당 멘토의 가입
  이메일을 공동 주최자로 등록한다(자동 녹화는 주최자·공동 주최자가 들어와야 시작, A52). 등록에
  실패하면 그 공간은 막고 실패로 돌려 다시 만들게 한다.
- 10분마다 `sync`가 빠진 공간을 채우고(시작 전 예정 세션), 취소된 세션의 공간을 막는다.
- Meet 설정이 없으면(클라이언트 None) 아무것도 하지 않는다. 설정이 갖춰지면 `sync`가 채운다.
외부 호출은 트랜잭션 밖에서 하고, 저장할 때만 세션을 잠근다. 잠그는 사이 다른 작업이 먼저 공간을
붙였으면 방금 만든 공간은 막아 둔다(고아 공간 방지).
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.domain.repositories import MentoringSessionRepository
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.integrations.google.meet import MeetSpace, MeetUnavailableError

logger = logging.getLogger(__name__)


class MeetClient(Protocol):
    async def create_space(self) -> MeetSpace: ...
    async def add_cohost(self, space_name: str, email: str) -> None: ...
    async def restrict_space(self, space_name: str) -> None: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...


class UserLookup(Protocol):
    """identity `UserQueries`."""

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]: ...


class MeetSpaceScheduler(Protocol):
    """승인 커밋 후 공간 생성을 워커로 보낸다 (app.state.meet_scheduler)."""

    async def space_needed(self, session_id: uuid.UUID) -> None: ...


class NoMeetScheduler:
    """보내지 않는다 (단위 테스트·주기 작업만 쓰는 곳)."""

    async def space_needed(self, session_id: uuid.UUID) -> None:
        return None


class MeetSpaceService:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        meet: MeetClient | None,
        mentors: MentorLookup,
        users: UserLookup,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._meet = meet
        self._mentors = mentors
        self._users = users
        self._uow = uow
        self._clock = clock

    @property
    def enabled(self) -> bool:
        return self._meet is not None

    async def ensure_space(self, session_id: uuid.UUID) -> bool:
        """공간이 필요하면 만들어 붙인다. 붙였으면 True. 실패는 MeetUnavailableError."""
        if self._meet is None:
            return False
        session = await self._sessions.get(session_id)
        if session is None or not session.needs_space:
            return False
        space = await self._meet.create_space()
        email = await self._mentor_email(session.mentor_id)
        if email:
            try:
                await self._meet.add_cohost(space.name, email)
            except MeetUnavailableError:
                await self._meet.restrict_space(space.name)  # 공동 주최자 없는 공간은 쓰지 않는다
                raise
        else:
            logger.warning(
                "멘토 이메일이 없어 공동 주최자 없이 공간을 붙인다 (세션 %s)", session_id
            )
        async with self._uow:
            locked = await self._sessions.lock(session_id)
            attached = locked is not None and locked.needs_space
            if locked is not None and attached:
                locked.attach_space(space.name, space.meeting_uri)
                await self._sessions.save(locked)
        if not attached:  # 잠그는 사이 취소됐거나 다른 작업이 먼저 붙였다
            await self._meet.restrict_space(space.name)
        return attached

    async def _mentor_email(self, mentor_id: uuid.UUID) -> str | None:
        mentor = await self._mentors.get(mentor_id)
        if mentor is None:
            return None
        user = (await self._users.get_many([mentor.account_id])).get(mentor.account_id)
        return user.email if user else None

    async def close_space(self, session_id: uuid.UUID) -> bool:
        """취소된 세션의 공간을 막고 링크를 지운다. 막았으면 True."""
        if self._meet is None:
            return False
        session = await self._sessions.get(session_id)
        if session is None or not session.needs_space_closed or not session.google_space_name:
            return False
        await self._meet.restrict_space(session.google_space_name)
        async with self._uow:
            locked = await self._sessions.lock(session_id)
            if locked is not None and locked.needs_space_closed:
                locked.space_closed()
                await self._sessions.save(locked)
        return True

    async def sync(self) -> tuple[int, int]:
        """(만든 공간 수, 막은 공간 수). 건별 실패는 로그만 남기고 다음 주기에 다시 한다."""
        if self._meet is None:
            return 0, 0
        created = closed = 0
        for session in await self._sessions.list_needing_space(self._clock.now()):
            created += await self._try(self.ensure_space, session.id, "생성")
        for session in await self._sessions.list_needing_close():
            closed += await self._try(self.close_space, session.id, "막기")
        return created, closed

    @staticmethod
    async def _try(
        action: Callable[[uuid.UUID], Awaitable[bool]], session_id: uuid.UUID, label: str
    ) -> int:
        try:
            done = await action(session_id)
        except MeetUnavailableError:
            logger.warning("Meet 공간 %s 실패 (세션 %s), 다음 주기에 다시 한다", label, session_id)
            return 0
        return 1 if done else 0

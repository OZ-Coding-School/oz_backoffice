"""세션 Meet 공간 생성·막기·주기 보완 (인메모리 + 가짜 Meet, A48)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.application.meet_service import MeetSpaceService
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.integrations.google.meet import MeetSpace
from app.shared.ids import new_id
from tests.fakes.mentoring import (
    FakeMeetClient,
    InMemoryRequestRepository,
    InMemorySessionRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)


class Harness:
    def __init__(self) -> None:
        self.sessions = InMemorySessionRepository(InMemoryRequestRepository())
        self.meet = FakeMeetClient()
        self.service = MeetSpaceService(
            sessions=self.sessions, meet=self.meet, uow=FakeUnitOfWork(), clock=FixedClock(NOW)
        )

    async def session(self, hours: int = 24) -> MentoringSession:
        start = NOW + timedelta(hours=hours)
        session = MentoringSession(
            mentor_id=new_id(),
            request_id=new_id(),
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            title="제목",
            topic="주제",
        )
        await self.sessions.add(session)
        return session


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_ensure_space_attaches_once(h: Harness) -> None:
    session = await h.session()
    assert await h.service.ensure_space(session.id)
    stored = h.sessions.items[session.id]
    assert (stored.google_space_name, stored.google_meet_url) == (
        "spaces/s1",
        "https://meet.google.com/s1",
    )
    assert not await h.service.ensure_space(session.id)  # 이미 있음
    assert not await h.service.ensure_space(new_id())
    assert h.meet.created == ["spaces/s1"]


async def test_close_space_and_sync(h: Harness) -> None:
    upcoming, started, canceled = await h.session(), await h.session(-1), await h.session(48)
    await h.service.ensure_space(canceled.id)
    h.sessions.items[canceled.id].status = MentoringSessionStatus.CANCELED

    created, closed = await h.service.sync()
    assert (created, closed) == (1, 1)  # 시작한 세션에는 만들지 않는다
    assert h.sessions.items[upcoming.id].google_space_name is not None
    assert h.sessions.items[started.id].google_space_name is None
    closed_session = h.sessions.items[canceled.id]
    assert (closed_session.google_space_name, closed_session.google_meet_url) == ("spaces/s1", None)
    assert h.meet.restricted == ["spaces/s1"]
    assert await h.service.sync() == (0, 0)  # 멱등


async def test_failures_are_retried_next_cycle(h: Harness) -> None:
    session = await h.session()
    h.meet.fail_create = 1
    assert await h.service.sync() == (0, 0)  # 실패는 로그만, 다음 주기에 다시
    assert await h.service.sync() == (1, 0)
    assert h.sessions.items[session.id].google_space_name == "spaces/s1"


async def test_canceled_while_creating_restricts_orphan(h: Harness) -> None:
    session = await h.session()

    original = h.meet.create_space

    async def create_then_cancel() -> MeetSpace:
        space = await original()
        h.sessions.items[session.id].status = MentoringSessionStatus.CANCELED  # 그 사이 취소됨
        return space

    h.meet.create_space = create_then_cancel  # type: ignore[method-assign]  # 경합 흉내
    assert not await h.service.ensure_space(session.id)
    assert h.meet.restricted == ["spaces/s1"]
    assert h.sessions.items[session.id].google_space_name is None


async def test_disabled_does_nothing(h: Harness) -> None:
    await h.session()
    service = MeetSpaceService(
        sessions=h.sessions, meet=None, uow=FakeUnitOfWork(), clock=FixedClock(NOW)
    )
    assert not service.enabled
    assert await service.sync() == (0, 0)

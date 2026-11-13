"""Meet 이벤트 처리: 도메인 규칙·서비스 (인메모리 + 가짜 이벤트 원천, A49·M27)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.application.meet_event_service import MeetEventService
from app.contexts.mentoring.domain.enums import MentoringSessionStatus, RecordingStatus
from app.contexts.mentoring.domain.session import MentoringSession
from app.integrations.google.meet import MeetUnavailableError
from app.integrations.google.meet_events import (
    CONFERENCE_ENDED,
    CONFERENCE_STARTED,
    RECORDING_GENERATED,
    TRANSCRIPT_GENERATED,
    ConferenceInfo,
    MeetEvent,
)
from app.shared.ids import new_id
from tests.fakes.mentoring import InMemoryRequestRepository, InMemorySessionRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

T = datetime(2026, 11, 20, 5, tzinfo=UTC)


def _session() -> MentoringSession:
    session = MentoringSession(
        mentor_id=new_id(),
        request_id=new_id(),
        starts_at=T,
        ends_at=T + timedelta(hours=1),
        title="제목",
        topic="주제",
    )
    session.attach_space("spaces/a", "https://meet.google.com/a")
    return session


def test_conference_times_keep_first_start_and_last_end() -> None:
    session = _session()
    assert session.conference_ended("conferenceRecords/2", T + timedelta(minutes=50))  # 순서 뒤바뀜
    assert session.status is MentoringSessionStatus.IN_PROGRESS
    assert session.conference_started("conferenceRecords/1", T)
    assert session.conference_started("conferenceRecords/2", T + timedelta(minutes=20)) is False
    assert session.conference_ended("conferenceRecords/1", T + timedelta(minutes=10)) is False
    assert (session.actual_started_at, session.actual_ended_at) == (T, T + timedelta(minutes=50))
    assert session.google_conference_record_name == "conferenceRecords/2"  # 처음 받은 회의 기록
    assert session.recording_generated()
    assert not session.recording_generated()

    session.status = MentoringSessionStatus.COMPLETED  # 멘토 기록 후에도 상태는 그대로
    assert session.conference_ended("conferenceRecords/3", T + timedelta(hours=2))
    assert session.status is MentoringSessionStatus.COMPLETED

    canceled = _session()
    canceled.cancel()
    assert not canceled.conference_started("conferenceRecords/9", T)
    assert not canceled.recording_generated()


class FakeSource:
    def __init__(self) -> None:
        self.records: dict[str, ConferenceInfo] = {}
        self.fail_records: set[str] = set()

    async def ensure_subscription(self) -> str:
        return "created"

    async def get_conference(self, record_name: str) -> ConferenceInfo | None:
        if record_name in self.fail_records:
            raise MeetUnavailableError()
        return self.records.get(record_name)


class Collects:
    def __init__(self) -> None:
        self.sessions: list[uuid.UUID] = []

    async def collect_needed(self, session_id: uuid.UUID) -> None:
        self.sessions.append(session_id)


class Seen:
    def __init__(self) -> None:
        self.ids: set[str] = set()

    async def seen(self, event_id: str) -> bool:
        return event_id in self.ids

    async def mark(self, event_id: str) -> None:
        self.ids.add(event_id)


def _event(n: int, kind: str, resource: str) -> MeetEvent:
    return MeetEvent(event_id=f"ev{n}", event_type=kind, resource_name=resource)


async def test_handle_applies_events_idempotently() -> None:
    sessions = InMemorySessionRepository(InMemoryRequestRepository())
    session = _session()
    await sessions.add(session)
    source, seen = FakeSource(), Seen()
    source.records = {
        "conferenceRecords/1": ConferenceInfo(
            "conferenceRecords/1", "spaces/a", T, T + timedelta(minutes=55)
        ),
        "conferenceRecords/x": ConferenceInfo("conferenceRecords/x", "spaces/other", T, None),
    }
    source.fail_records = {"conferenceRecords/fail"}
    collects = Collects()
    service = MeetEventService(
        sessions=sessions, source=source, processed=seen, artifacts=collects, uow=FakeUnitOfWork()
    )
    started = _event(1, CONFERENCE_STARTED, "conferenceRecords/1")
    assert await service.handle(started)
    assert not await service.handle(started)  # 중복 수신
    for event in (
        _event(2, CONFERENCE_ENDED, "conferenceRecords/1"),
        _event(3, RECORDING_GENERATED, "conferenceRecords/1/recordings/r1"),
        _event(4, TRANSCRIPT_GENERATED, "conferenceRecords/1/transcripts/t1"),  # P13
        _event(5, CONFERENCE_STARTED, "conferenceRecords/x"),  # 멘토링 공간 아님
        _event(6, CONFERENCE_STARTED, "conferenceRecords/gone"),  # 사라진 회의 기록
    ):
        assert await service.handle(event)
    with pytest.raises(MeetUnavailableError):  # Google 오류는 작업이 재시도
        await service.handle(_event(7, CONFERENCE_STARTED, "conferenceRecords/fail"))
    assert "ev7" not in seen.ids
    stored = sessions.items[session.id]
    assert (stored.status, stored.actual_started_at, stored.actual_ended_at) == (
        MentoringSessionStatus.IN_PROGRESS,
        T,
        T + timedelta(minutes=55),
    )
    assert stored.recording_status is RecordingStatus.FILE_GENERATED
    assert collects.sessions == [session.id, session.id]  # 녹화·전사 생성 → 수집 요청
    assert await service.ensure_subscription() == "created"

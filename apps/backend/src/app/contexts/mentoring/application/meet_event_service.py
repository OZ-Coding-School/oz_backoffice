"""Meet 이벤트 처리 (decisions A49·M18·M27, P12-2).

- 구독: 주최 계정 하나를 구독하고 주기적으로 갱신한다(`ensure_subscription`).
- 수신: worker의 실시간 수신기가 이벤트마다 작업을 등록하고(A50), 작업이 `handle`을 부른다. 처리에
  실패하면(Google 오류) 예외를 그대로 올려 작업이 재시도한다. 처리한 이벤트 ID는 7일 동안 기억해
  중복을 거른다.
- 회의 시작·종료: 회의 기록을 조회해 공간 → 세션을 찾고 IN_PROGRESS·실제 시작(처음)·종료(마지막)·첫
  회의 기록 이름을 남긴다. 완료·노쇼는 멘토 기록으로만 정한다(M27).
- 녹화 생성: 녹화 상태 FILE_GENERATED. 녹화·전사·스마트 메모 생성 이벤트는 그 세션 파일 수집을
  워커로 보낸다(P13-2).
- 멘토링 세션이 아닌 공간, 취소된 세션, 사라진 회의 기록은 무시한다(ack).
"""

import logging
import uuid
from typing import Protocol

from app.contexts.mentoring.domain.repositories import MentoringSessionRepository
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.uow import UnitOfWork
from app.integrations.google.meet_events import (
    CONFERENCE_ENDED,
    CONFERENCE_STARTED,
    RECORDING_GENERATED,
    SMART_NOTE_GENERATED,
    TRANSCRIPT_GENERATED,
    ConferenceInfo,
    MeetEvent,
)

logger = logging.getLogger(__name__)


class MeetEventSource(Protocol):
    async def ensure_subscription(self) -> str: ...
    async def get_conference(self, record_name: str) -> ConferenceInfo | None: ...


class ProcessedEvents(Protocol):
    async def seen(self, event_id: str) -> bool: ...
    async def mark(self, event_id: str) -> None: ...


class ArtifactScheduler(Protocol):
    """파일 생성 이벤트를 받으면 그 세션 녹화 수집을 워커로 보낸다 (P13-2)."""

    async def collect_needed(self, session_id: uuid.UUID) -> None: ...


FILE_EVENTS = (RECORDING_GENERATED, TRANSCRIPT_GENERATED, SMART_NOTE_GENERATED)


class MeetEventService:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        source: MeetEventSource,
        processed: ProcessedEvents,
        artifacts: ArtifactScheduler,
        uow: UnitOfWork,
    ) -> None:
        self._sessions = sessions
        self._source = source
        self._processed = processed
        self._artifacts = artifacts
        self._uow = uow

    async def ensure_subscription(self) -> str:
        return await self._source.ensure_subscription()

    async def handle(self, event: MeetEvent) -> bool:
        """처리했으면 True, 이미 처리한 이벤트면 False. Google 오류는 MeetUnavailableError."""
        if await self._processed.seen(event.event_id):
            return False
        await self._handle(event)
        await self._processed.mark(event.event_id)
        return True

    async def _handle(self, event: MeetEvent) -> None:
        if event.event_type not in (CONFERENCE_STARTED, CONFERENCE_ENDED, *FILE_EVENTS):
            logger.info("모르는 Meet 이벤트 %s", event.event_type)
            return
        record = await self._source.get_conference(event.conference_record_name)
        if record is None:
            return
        found = await self._sessions.get_by_space(record.space_name)
        if found is None:
            return  # 멘토링 세션이 아닌 공간
        async with self._uow:
            session = await self._sessions.lock(found.id)
            if session is not None and self._apply(session, event, record):
                await self._sessions.save(session)
        if event.event_type in FILE_EVENTS:
            await self._artifacts.collect_needed(found.id)

    @staticmethod
    def _apply(session: MentoringSession, event: MeetEvent, record: ConferenceInfo) -> bool:
        if event.event_type == CONFERENCE_STARTED:
            return session.conference_started(record.name, record.start_time)
        if event.event_type == CONFERENCE_ENDED:
            return session.conference_ended(record.name, record.end_time)
        if event.event_type == RECORDING_GENERATED:
            return session.recording_generated()
        return False

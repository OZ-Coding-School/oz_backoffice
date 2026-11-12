"""불가 시간 변경과 신청·세션의 충돌 (decisions A37·A42).

- 대기 신청: 아직 승인할 수 있는(시작 전) 희망 일시가 **모두** 불가 시간에 걸리면 충돌이다.
  하나라도 남으면 멘토가 그 일시로 승인할 수 있으므로 충돌이 아니다.
- 예정 세션: 시작 전 세션이 불가 시간과 겹치면 충돌이다.
confirm하면 충돌 대기 신청은 반려(RELEASE, 사유 '멘토 일정 변경'), 세션은 취소하고 전액 환불한다.
"""

import uuid
from datetime import datetime

from app.contexts.mentoring.application.request_cleanup import SCHEDULE_CONFLICT, RequestCleanup
from app.contexts.mentoring.application.schedule_service import ScheduleConflict
from app.contexts.mentoring.domain.repositories import (
    MentoringRequestRepository,
    MentoringSessionRepository,
)
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.core.clock import Clock


def _blocked(start: datetime, end: datetime, unavailable: list[MentorUnavailablePeriod]) -> bool:
    return any(next(p.occurrences(start, end), None) is not None for p in unavailable)


class SessionScheduleConflicts:
    def __init__(
        self,
        *,
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
        cleanup: RequestCleanup,
        clock: Clock,
    ) -> None:
        self._requests = requests
        self._sessions = sessions
        self._cleanup = cleanup
        self._clock = clock

    async def find(
        self, mentor_id: uuid.UUID, unavailable: list[MentorUnavailablePeriod]
    ) -> list[ScheduleConflict]:
        now = self._clock.now()
        conflicts: list[ScheduleConflict] = []
        for request in await self._requests.list_pending(mentor_id=mentor_id):
            slots = [(s, e) for s, e in request.slots() if s > now]
            if slots and all(_blocked(s, e, unavailable) for s, e in slots):
                start, end = min(slots)
                conflicts.append(ScheduleConflict("REQUEST", request.id, start, end))
        for session in await self._sessions.list_upcoming(now, mentor_id=mentor_id):
            if _blocked(session.starts_at, session.ends_at, unavailable):
                conflicts.append(
                    ScheduleConflict("SESSION", session.id, session.starts_at, session.ends_at)
                )
        return conflicts

    async def resolve(self, conflicts: list[ScheduleConflict], *, actor_id: uuid.UUID) -> None:
        request_ids = [c.target_id for c in conflicts if c.kind == "REQUEST"]
        session_ids = {c.target_id for c in conflicts if c.kind == "SESSION"}
        if request_ids:
            found = await self._requests.get_many(request_ids)
            await self._cleanup.cancel_pending(
                list(found.values()), SCHEDULE_CONFLICT, actor_id=actor_id, reject=True
            )
        if session_ids:
            sessions = [s for s in [await self._sessions.get(i) for i in session_ids] if s]
            await self._cleanup.cancel_sessions(
                sessions, SCHEDULE_CONFLICT, refund=True, actor_id=actor_id
            )

"""불가 시간 충돌 검사·정리 (인메모리, A37·A42)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.schedule_conflicts import SessionScheduleConflicts
from app.contexts.mentoring.domain.enums import (
    MentoringRequestStatus,
    MentoringSessionStatus,
    UnavailableRepeat,
)
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.mentoring import CleanupStores

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)
T = datetime(2026, 11, 16, 14, tzinfo=KST)  # 월요일 14:00


async def test_find_and_resolve() -> None:
    clock = FixedClock(NOW)
    stores = CleanupStores(AuditRecorder(InMemoryAuditLogRepository(), clock), clock)
    finder = SessionScheduleConflicts(
        requests=stores.requests, sessions=stores.sessions, cleanup=stores.cleanup, clock=clock
    )
    mentor = new_id()
    blocked = await stores.pending(mentor_id=mentor, at=T)
    stores.requests.items[blocked.id].desired_times = [T, T + timedelta(days=1)]
    partly = await stores.pending(mentor_id=mentor, at=T)
    stores.requests.items[partly.id].desired_times = [T, T + timedelta(days=1, hours=5)]
    session_request = await stores.pending(mentor_id=mentor, at=T + timedelta(days=2))
    stored = stores.requests.items[session_request.id]
    start, end = stored.approve(T + timedelta(days=2), now=NOW)
    (owned,) = await stores.accounts.find_by_owners(student_ids=[stored.requester_id], team_ids=[])
    account = stores.accounts.items[owned.id]
    account.use(60, request_id=stored.id, reason="승인")
    session = MentoringSession(
        mentor_id=mentor, request_id=stored.id, starts_at=start, ends_at=end, title="t", topic="t"
    )
    await stores.sessions.add(session)
    await stores.pending(mentor_id=new_id(), at=T)  # 다른 멘토

    # 매일 13:00~16:00 불가 → 14시 희망은 모두 막힘, 19시 희망이 있는 신청은 승인 가능
    daily = MentorUnavailablePeriod(
        mentor_id=mentor,
        repeat=UnavailableRepeat.DAILY,
        starts_at=datetime(2026, 11, 12, 13, tzinfo=KST),
        ends_at=datetime(2026, 11, 12, 16, tzinfo=KST),
    )
    conflicts = await finder.find(mentor, [daily])
    assert {(c.kind, c.target_id) for c in conflicts} == {
        ("REQUEST", blocked.id),
        ("SESSION", session.id),
    }
    assert await finder.find(mentor, []) == []

    await finder.resolve(conflicts, actor_id=new_id())
    rejected = stores.requests.items[blocked.id]
    assert (rejected.status, rejected.reject_reason) == (
        MentoringRequestStatus.REJECTED,
        "멘토 일정 변경",
    )
    assert stores.status(partly) is MentoringRequestStatus.PENDING
    assert stores.sessions.items[session.id].status is MentoringSessionStatus.CANCELED
    assert stores.requests.items[session_request.id].status is MentoringRequestStatus.CANCELED
    assert stores.accounts.items[owned.id].used_minutes == 0  # 전액 환불

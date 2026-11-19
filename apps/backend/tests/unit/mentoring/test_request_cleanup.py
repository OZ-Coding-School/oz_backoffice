"""신청·세션 자동 정리 (인메모리, A37·A42·A45)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.request_cleanup import RequestCleanup
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringCancelActor,
    MentoringRequestStatus,
    MentoringSessionStatus,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemoryRequestRepository,
    InMemorySessionRepository,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)
T = datetime(2026, 11, 16, 14, tzinfo=KST)


class Harness:
    def __init__(self) -> None:
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.audit_logs = InMemoryAuditLogRepository()
        clock = FixedClock(NOW)
        self.cleanup = RequestCleanup(
            requests=self.requests,
            sessions=self.sessions,
            accounts=self.accounts,
            ledger=self.ledger,
            audit=AuditRecorder(self.audit_logs, clock),
            clock=clock,
        )
        self.mentor_id = new_id()

    async def account(self, **owner: Any) -> BalanceAccount:
        account = BalanceAccount(
            valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30), **owner
        )
        account.grant(300, "지급", today=date(2026, 11, 11))
        await self.accounts.add(account)
        return account

    async def pending(self, account: BalanceAccount, at: datetime = T) -> MentoringRequest:
        request = MentoringRequest(
            requester_id=account.student_id or new_id(),
            team_id=account.team_id,
            mentor_id=self.mentor_id,
            topic="주제",
            detail="내용",
            desired_times=[at],
            duration=60,
        )
        self.accounts.items[account.id].hold(60, request_id=request.id, reason="신청")
        await self.requests.add(request)
        return request

    async def approved(self, account: BalanceAccount, at: datetime = T) -> MentoringSession:
        request = await self.pending(account, at)
        stored = self.requests.items[request.id]
        start, end = stored.approve(at, now=NOW)
        self.accounts.items[account.id].use(60, request_id=request.id, reason="승인")
        session = MentoringSession(
            mentor_id=self.mentor_id,
            request_id=request.id,
            starts_at=start,
            ends_at=end,
            title="제목",
            topic="주제",
        )
        await self.sessions.add(session)
        return session


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_cancel_pending_releases_and_is_idempotent(h: Harness) -> None:
    solo = await h.account(student_id=new_id())
    team = await h.account(team_id=new_id())
    requests = [await h.pending(solo), await h.pending(team, T + timedelta(hours=2))]
    actor = new_id()
    assert await h.cleanup.cancel_pending(requests, "멘토 비활성화", actor_id=actor) == 2
    assert all(r.status is MentoringRequestStatus.CANCELED for r in h.requests.items.values())
    assert {r.canceled_by for r in h.requests.items.values()} == {MentoringCancelActor.SYSTEM}
    assert [h.accounts.items[a.id].held_minutes for a in (solo, team)] == [0, 0]
    assert [e.type for e in h.ledger.entries] == [MentoringBalanceTransactionType.RELEASE] * 2
    assert {log.actor_user_id for log in h.audit_logs.logs} == {actor}
    assert await h.cleanup.cancel_pending(requests, "다시", actor_id=None) == 0  # 이미 처리됨
    assert await h.cleanup.cancel_pending([], "없음", actor_id=None) == 0


async def test_reject_pending(h: Harness) -> None:
    account = await h.account(student_id=new_id())
    request = await h.pending(account)
    assert await h.cleanup.cancel_pending([request], "멘토 일정 변경", actor_id=None, reject=True)
    stored = h.requests.items[request.id]
    assert (stored.status, stored.reject_reason) == (
        MentoringRequestStatus.REJECTED,
        "멘토 일정 변경",
    )
    assert [log.action for log in h.audit_logs.logs] == ["mentoring.request.auto_reject"]


async def test_cancel_sessions_with_and_without_refund(h: Harness) -> None:
    account = await h.account(student_id=new_id())
    refunded = await h.approved(account)
    kept = await h.approved(account, T + timedelta(hours=3))
    assert await h.cleanup.cancel_sessions([refunded], "불가 시간", refund=True, actor_id=None) == 1
    assert await h.cleanup.cancel_sessions([kept], "수강 종료", refund=False, actor_id=None) == 1
    stored = h.accounts.items[account.id]
    assert (stored.used_minutes, stored.remaining_minutes) == (60, 240)
    assert {s.status for s in h.sessions.items.values()} == {MentoringSessionStatus.CANCELED}
    assert {r.status for r in h.requests.items.values()} == {MentoringRequestStatus.CANCELED}
    assert {r.canceled_by for r in h.requests.items.values()} == {MentoringCancelActor.SYSTEM}
    assert [e.type for e in h.ledger.entries] == [MentoringBalanceTransactionType.REFUND]
    assert await h.cleanup.cancel_sessions([kept], "다시", refund=True, actor_id=None) == 0

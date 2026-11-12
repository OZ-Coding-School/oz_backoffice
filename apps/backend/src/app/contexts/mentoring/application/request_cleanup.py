"""다른 변경에 따른 신청·세션 자동 정리 (decisions A37·A42·A45).

호출하는 서비스의 트랜잭션 안에서 쓴다(UoW를 열지 않는다).
- 대기 신청 자동 취소(RELEASE): 멘토 비활성화·배정 비활성화·신청 받기 끄기·팀 담당 멘토 변경·
  팀에서 빠진 신청자·수강 종료.
- 대기 신청 자동 반려(RELEASE): 불가 시간 충돌.
- 예정 세션 자동 취소: 불가 시간 충돌(전액 환불), 수강 종료 1:1(환불 없음).
잠금은 계좌(id 순) → 신청 → 세션 순서다. 잠그는 사이 상태가 바뀐 건은 건너뛴다(멱등).
"""

import uuid
from typing import Any

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringRequestStatus, MentoringSessionStatus
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import Clock

TARGET = "mentoring_request"
RELEASE_REASON = "신청 자동 취소"
REJECT_RELEASE_REASON = "신청 자동 반려"
REFUND_REASON = "세션 자동 취소"
MENTOR_DEACTIVATED = "멘토 비활성화로 자동 취소"
ASSIGNMENT_DEACTIVATED = "기수 배정 종료로 자동 취소"
ACCEPTING_OFF = "멘토가 신청 받기를 꺼 자동 취소"
TEAM_MENTOR_CHANGED = "팀 담당 멘토 변경으로 자동 취소"
LEFT_TEAM = "신청자가 팀에서 빠져 자동 취소"
ENROLLMENT_ENDED = "수강 종료로 자동 취소"
SCHEDULE_CONFLICT = "멘토 일정 변경"


def _owner(request: MentoringRequest) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """(1:1 수강생, 팀)."""
    return (None, request.team_id) if request.team_id else (request.requester_id, None)


class RequestCleanup:
    def __init__(
        self,
        *,
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        audit: AuditRecorder,
        clock: Clock,
    ) -> None:
        self._requests = requests
        self._sessions = sessions
        self._accounts = accounts
        self._ledger = ledger
        self._audit = audit
        self._clock = clock

    async def count_pending_where(self, **filters: Any) -> int:
        """`list_pending` 조건으로 대기 신청 수 (미리보기용)."""
        return len(await self._requests.list_pending(**filters))

    async def cancel_pending_where(
        self, reason: str, *, actor_id: uuid.UUID | None, **filters: Any
    ) -> int:
        """`list_pending` 조건에 맞는 대기 신청을 자동 취소한다."""
        items = await self._requests.list_pending(**filters)
        return await self.cancel_pending(items, reason, actor_id=actor_id)

    async def cancel_pending(
        self,
        items: list[MentoringRequest],
        reason: str,
        *,
        actor_id: uuid.UUID | None,
        reject: bool = False,
    ) -> int:
        """대기 신청을 취소(또는 반려)하고 보류를 돌려준다. 처리한 건수."""
        if not items:
            return 0
        accounts = await self._lock_accounts(items)
        now = self._clock.now()
        entries: list[BalanceTransaction] = []
        changed: dict[uuid.UUID, BalanceAccount] = {}
        for item in sorted(items, key=lambda r: r.id):
            request = await self._requests.lock(item.id)
            account = accounts.get(_owner(item))
            if request is None or account is None:
                continue
            if request.status is not MentoringRequestStatus.PENDING:
                continue
            if reject:
                request.reject(reason, now=now)
            else:
                request.cancel(reason, now=now)
            entries.append(
                account.release(
                    request.duration,
                    request_id=request.id,
                    reason=REJECT_RELEASE_REASON if reject else RELEASE_REASON,
                )
            )
            changed[account.id] = account
            await self._requests.save(request)
            await self._record(
                actor_id, "auto_reject" if reject else "auto_cancel", request, reason
            )
        await self._flush(changed, entries)
        return len(entries)

    async def cancel_sessions(
        self,
        items: list[MentoringSession],
        reason: str,
        *,
        refund: bool,
        actor_id: uuid.UUID | None,
    ) -> int:
        """예정 세션과 그 신청을 취소한다(환불은 선택). 처리한 건수."""
        if not items:
            return 0
        requests = await self._requests.get_many([s.request_id for s in items])
        accounts = await self._lock_accounts(list(requests.values()))
        now = self._clock.now()
        entries: list[BalanceTransaction] = []
        changed: dict[uuid.UUID, BalanceAccount] = {}
        done = 0
        for item in sorted(items, key=lambda s: s.request_id):
            request = await self._requests.lock(item.request_id)
            session = await self._sessions.lock_by_request(item.request_id)
            if request is None or session is None:
                continue
            if (
                request.status is not MentoringRequestStatus.APPROVED
                or session.status is not MentoringSessionStatus.SCHEDULED
            ):
                continue
            request.cancel(reason, now=now)
            session.cancel()
            account = accounts.get(_owner(request))
            if refund and account is not None:
                entries.append(
                    account.refund(request.duration, request_id=request.id, reason=REFUND_REASON)
                )
                changed[account.id] = account
            await self._requests.save(request)
            await self._sessions.save(session)
            await self._record(
                actor_id, "auto_cancel", request, reason, session=session, refund=refund
            )
            done += 1
        await self._flush(changed, entries)
        return done

    async def _lock_accounts(
        self, items: list[MentoringRequest]
    ) -> dict[tuple[uuid.UUID | None, uuid.UUID | None], BalanceAccount]:
        found = await self._accounts.find_by_owners(
            student_ids=list({r.requester_id for r in items if r.team_id is None}),
            team_ids=list({r.team_id for r in items if r.team_id is not None}),
        )
        locked = await self._accounts.lock_many([a.id for a in found])
        return {(a.student_id, a.team_id): a for a in locked}

    async def _flush(
        self, changed: dict[uuid.UUID, BalanceAccount], entries: list[BalanceTransaction]
    ) -> None:
        for account in changed.values():
            await self._accounts.save(account)
        if entries:
            await self._ledger.add_many(entries)

    async def _record(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        request: MentoringRequest,
        reason: str,
        *,
        session: MentoringSession | None = None,
        refund: bool | None = None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,  # 원인이 된 변경을 한 사람 (작업이면 None)
            action=f"mentoring.request.{action}",
            target_type=TARGET,
            target_id=request.id,
            after={
                "status": request.status.value,
                "reason": reason,
                "session_id": str(session.id) if session else None,
                "refund": refund,
            },
        )

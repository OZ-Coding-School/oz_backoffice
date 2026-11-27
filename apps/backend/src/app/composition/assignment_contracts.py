"""계약 변화 → 기수 배정 정리 조립 (decisions A110).

educator 계약 서비스의 `ContractLifecycleListener`를 멘토링 `AssignmentContractSync`로 채운다.
계약 서비스의 트랜잭션 안에서 불린다.
자동 취소한 대기 신청의 채팅 안내는 보내지 않는다(감사 로그만).
"""

import uuid
from datetime import date

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.contract_sync import AssignmentContractSync
from app.contexts.mentoring.application.request_cleanup import RequestCleanup
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentorRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
)
from app.core.clock import Clock


class AssignmentContractListener:
    def __init__(self, *, audit: AuditRecorder, clock: Clock) -> None:
        self._audit = audit
        self._clock = clock

    def _sync(self) -> AssignmentContractSync:
        return AssignmentContractSync(
            assignments=TortoiseCohortMentorRepository(),
            cleanup=RequestCleanup(
                requests=TortoiseMentoringRequestRepository(),
                sessions=TortoiseMentoringSessionRepository(),
                accounts=TortoiseBalanceAccountRepository(),
                ledger=TortoiseBalanceTransactionRepository(),
                audit=self._audit,
                clock=self._clock,
            ),
            audit=self._audit,
            clock=self._clock,
        )

    async def contract_closed(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        await self._sync().contract_closed(contract_id, actor_id=actor_id)

    async def contract_period_changed(
        self,
        contract_id: uuid.UUID,
        *,
        start_date: date | None,
        end_date: date | None,
        actor_id: uuid.UUID | None,
    ) -> None:
        await self._sync().contract_period_changed(
            contract_id, start_date=start_date, end_date=end_date, actor_id=actor_id
        )

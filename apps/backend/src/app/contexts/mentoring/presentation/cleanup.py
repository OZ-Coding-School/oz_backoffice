"""신청·세션 자동 정리 도구 조립 (여러 라우터가 같이 쓴다)."""

from typing import cast

from fastapi import Request

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.request_cleanup import RequestCleanup
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
)
from app.core.clock import Clock


def build_cleanup(request: Request, clock: Clock) -> RequestCleanup:
    return RequestCleanup(
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        clock=clock,
    )

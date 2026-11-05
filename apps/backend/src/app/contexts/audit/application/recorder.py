"""감사 로그 기록 (다른 컨텍스트가 호출하는 공개 서비스).

호출하는 서비스의 UnitOfWork 안에서 호출하면 업무 변경과 같은 트랜잭션으로 저장된다.
"""

import uuid
from typing import Any

from app.contexts.audit.domain.entities import AuditLog
from app.contexts.audit.domain.repositories import AuditLogRepository
from app.core.clock import Clock


class AuditRecorder:
    def __init__(self, repository: AuditLogRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def record(
        self,
        *,
        actor_user_id: uuid.UUID | None,
        action: str,
        target_type: str,
        target_id: uuid.UUID | None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            ip=ip,
            created_at=self._clock.now(),
        )
        await self._repository.add(log)
        return log

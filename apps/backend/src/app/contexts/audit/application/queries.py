"""감사 기록 조회 (다른 컨텍스트가 이력을 보여 줄 때 쓰는 공개 서비스)."""

import uuid

from app.contexts.audit.domain.entities import AuditLog
from app.contexts.audit.domain.repositories import AuditLogRepository


class AuditQueries:
    def __init__(self, logs: AuditLogRepository) -> None:
        self._logs = logs

    async def list_for_target(
        self, target_type: str, target_id: uuid.UUID, *, actions: frozenset[str], limit: int = 50
    ) -> list[AuditLog]:
        """그 대상의 감사 기록 중 actions만, 최신순."""
        logs = await self._logs.list_for_target(target_type, target_id, limit=limit)
        return [log for log in logs if log.action in actions]

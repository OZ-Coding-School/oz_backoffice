"""audit 리포지토리 인터페이스."""

import uuid
from typing import Protocol

from app.contexts.audit.domain.entities import AuditLog


class AuditLogRepository(Protocol):
    async def add(self, log: AuditLog) -> None: ...

    async def list_for_target(
        self,
        target_type: str,
        target_id: uuid.UUID,
        *,
        limit: int,
        before: uuid.UUID | None = None,
    ) -> list[AuditLog]:
        """최신순. before(uuid7)보다 이전 로그만 (커서 페이지네이션)."""
        ...

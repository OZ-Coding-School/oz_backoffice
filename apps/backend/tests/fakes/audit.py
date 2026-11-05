"""audit 인메모리 리포지토리."""

import uuid

from app.contexts.audit.domain.entities import AuditLog


class InMemoryAuditLogRepository:
    def __init__(self) -> None:
        self.logs: list[AuditLog] = []

    async def add(self, log: AuditLog) -> None:
        self.logs.append(log)

    async def list_for_target(
        self,
        target_type: str,
        target_id: uuid.UUID,
        *,
        limit: int,
        before: uuid.UUID | None = None,
    ) -> list[AuditLog]:
        matched = [
            log
            for log in self.logs
            if log.target_type == target_type
            and log.target_id == target_id
            and (before is None or log.id < before)
        ]
        return sorted(matched, key=lambda log: log.id, reverse=True)[:limit]

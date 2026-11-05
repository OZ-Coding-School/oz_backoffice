"""audit 리포지토리 구현 (Tortoise)."""

import uuid

from app.contexts.audit.domain.entities import AuditLog
from app.contexts.audit.infrastructure.models import AuditLogModel


def _to_entity(model: AuditLogModel) -> AuditLog:
    return AuditLog(
        id=model.id,
        actor_user_id=model.actor_user_id,  # type: ignore[attr-defined]  # FK 컬럼 속성
        action=model.action,
        target_type=model.target_type,
        target_id=model.target_id,
        before=model.before,
        after=model.after,
        ip=model.ip,
        created_at=model.created_at,
    )


class TortoiseAuditLogRepository:
    async def add(self, log: AuditLog) -> None:
        await AuditLogModel.create(
            id=log.id,
            actor_user_id=log.actor_user_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            before=log.before,
            after=log.after,
            ip=log.ip,
            created_at=log.created_at,
        )

    async def list_for_target(
        self,
        target_type: str,
        target_id: uuid.UUID,
        *,
        limit: int,
        before: uuid.UUID | None = None,
    ) -> list[AuditLog]:
        query = AuditLogModel.filter(target_type=target_type, target_id=target_id)
        if before is not None:
            query = query.filter(id__lt=before)
        models = await query.order_by("-id").limit(limit)
        return [_to_entity(m) for m in models]

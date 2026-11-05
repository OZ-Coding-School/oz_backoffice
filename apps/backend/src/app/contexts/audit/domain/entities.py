"""audit 도메인 엔티티."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.shared.domain import Entity
from app.shared.errors import BusinessRuleViolation

ACTION_MAX_LENGTH = 100
TARGET_TYPE_MAX_LENGTH = 50


@dataclass(kw_only=True, eq=False)
class AuditLog(Entity):
    """감사 로그 (append-only). actor가 None이면 시스템 작업이다.

    action 예: "mentoring.balance.grant", target_type 예: "mentoring_balance_account"
    """

    action: str
    target_type: str
    target_id: uuid.UUID | None
    created_at: datetime
    actor_user_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None

    def __post_init__(self) -> None:
        if not self.action or len(self.action) > ACTION_MAX_LENGTH:
            raise BusinessRuleViolation(
                "감사 로그 action이 올바르지 않습니다.", code="invalid_audit_log"
            )
        if not self.target_type or len(self.target_type) > TARGET_TYPE_MAX_LENGTH:
            raise BusinessRuleViolation(
                "감사 로그 target_type이 올바르지 않습니다.", code="invalid_audit_log"
            )

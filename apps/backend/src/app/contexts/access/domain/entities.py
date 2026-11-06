"""access 도메인: 사용자 역할 부여 (범위 기반 RBAC, decisions D4)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.access.domain.catalog import ROLES_BY_CODE
from app.contexts.access.domain.enums import RoleScopeType
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation


@dataclass(kw_only=True, eq=False)
class UserRole(AggregateRoot):
    """역할 부여 1건. GLOBAL이면 scope_id가 없고, BOOTCAMP·COHORT면 과정·기수 ID다."""

    user_id: uuid.UUID
    role_code: str
    scope_type: RoleScopeType
    scope_id: uuid.UUID | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        role = ROLES_BY_CODE.get(self.role_code)
        if role is None:
            raise BusinessRuleViolation("존재하지 않는 역할입니다.", code="role_not_found")
        if (self.scope_type is RoleScopeType.GLOBAL) != (self.scope_id is None):
            raise BusinessRuleViolation(
                "전체 범위만 대상 없이 부여할 수 있습니다.", code="invalid_role_scope"
            )
        if self.scope_type not in role.scopes:
            raise BusinessRuleViolation(
                f"{role.name} 역할은 이 범위로 부여할 수 없습니다.", code="invalid_role_scope"
            )

    def is_effective(self, now: datetime) -> bool:
        return self.expires_at is None or self.expires_at > now


@dataclass(frozen=True, slots=True)
class RoleGrant:
    """조회용: 사용자가 가진 역할 (역할 코드 + 범위)."""

    role_code: str
    scope_type: RoleScopeType
    scope_id: uuid.UUID | None
    expires_at: datetime | None

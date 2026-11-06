"""access 인메모리 리포지토리."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from app.contexts.access.domain.catalog import RoleDefinition
from app.contexts.access.domain.entities import RoleGrant, UserRole


class InMemoryRoleCatalogRepository:
    def __init__(self) -> None:
        self.roles: dict[str, frozenset[str]] = {}
        self.sync_count = 0

    async def sync(self, roles: Sequence[RoleDefinition], permissions: dict[str, str]) -> None:
        self.sync_count += 1
        self.roles = {role.code: role.permissions for role in roles}


class InMemoryUserRoleRepository:
    def __init__(self) -> None:
        self.items: list[UserRole] = []

    async def add(self, user_role: UserRole) -> None:
        self.items.append(user_role)

    async def exists(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        return any(
            (r.user_id, r.role_code, r.scope_type, r.scope_id)
            == (user_id, role_code, scope_type, scope_id)
            for r in self.items
        )

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        return [
            RoleGrant(r.role_code, r.scope_type, r.scope_id, r.expires_at)
            for r in self.items
            if r.user_id == user_id and r.is_effective(now)
        ]

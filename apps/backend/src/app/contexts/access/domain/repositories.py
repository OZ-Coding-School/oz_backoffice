"""access 리포지토리 인터페이스."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.contexts.access.domain.catalog import RoleDefinition
from app.contexts.access.domain.entities import RoleGrant, UserRole


class RoleCatalogRepository(Protocol):
    async def sync(self, roles: Sequence[RoleDefinition], permissions: dict[str, str]) -> None:
        """역할·권한·역할-권한 매핑을 정의와 같게 맞춘다 (멱등)."""
        ...


class UserRoleRepository(Protocol):
    async def add(self, user_role: UserRole) -> None: ...
    async def exists(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool: ...
    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        """만료되지 않은 역할만."""
        ...

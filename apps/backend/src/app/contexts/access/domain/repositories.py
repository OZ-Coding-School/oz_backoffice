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
    async def remove(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        """해당 역할 부여를 지운다. 지운 것이 있으면 True."""
        ...

    async def get(self, user_role_id: uuid.UUID) -> UserRole | None: ...

    async def delete(self, user_role_id: uuid.UUID) -> None: ...

    async def list_by_user(self, user_id: uuid.UUID) -> list[UserRole]:
        """만료된 것까지 모두 (관리 화면용)."""
        ...

    async def lock_effective_holders(self, role_code: str, *, now: datetime) -> list[uuid.UUID]:
        """역할을 가진(만료되지 않은) 회원 ID. 행을 잠가 동시 회수 경합을 막는다 (UoW 안에서)."""
        ...

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        """만료되지 않은 역할만."""
        ...

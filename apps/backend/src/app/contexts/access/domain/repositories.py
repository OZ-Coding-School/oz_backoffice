"""access 리포지토리 인터페이스."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.contexts.access.domain.catalog import RoleDefinition
from app.contexts.access.domain.entities import RoleGrant, UserRole
from app.contexts.access.domain.roles import Role


class RoleCatalogRepository(Protocol):
    async def sync(self, roles: Sequence[RoleDefinition], permissions: dict[str, str]) -> None:
        """없는 권한·역할만 만든다 (멱등, A84).

        권한 설명은 정의대로 고친다. 역할을 새로 만들 때만 초기 권한 묶음을 넣고, 이미 있는
        역할의 이름·설명·매핑은 덮지 않는다. 최고 관리자에게는 빠진 권한을 더한다.
        """
        ...


class RoleRepository(Protocol):
    async def list_all(self) -> list[Role]:
        """기본 역할(정의 순서) → 새 역할(만든 순서)."""
        ...

    async def get(self, code: str) -> Role | None: ...
    async def lock(self, code: str) -> Role | None:
        """행을 잠가 읽는다 (UoW 안에서)."""
        ...

    async def name_taken(self, name: str, *, exclude_code: str | None = None) -> bool: ...
    async def add(self, role: Role) -> None: ...
    async def save(self, role: Role) -> None:
        """이름·설명·권한 묶음을 저장한다."""
        ...

    async def delete(self, code: str) -> None: ...
    async def holder_counts(self) -> dict[str, int]:
        """역할별 부여받은 회원 수 (만료된 부여 포함)."""
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

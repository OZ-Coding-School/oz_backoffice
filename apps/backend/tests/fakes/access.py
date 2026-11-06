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

    async def remove(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        key = (user_id, role_code, scope_type, scope_id)
        before = len(self.items)
        self.items = [
            r for r in self.items if (r.user_id, r.role_code, r.scope_type, r.scope_id) != key
        ]
        return len(self.items) < before

    async def get(self, user_role_id: uuid.UUID) -> UserRole | None:
        return next((r for r in self.items if r.id == user_role_id), None)

    async def delete(self, user_role_id: uuid.UUID) -> None:
        self.items = [r for r in self.items if r.id != user_role_id]

    async def list_by_user(self, user_id: uuid.UUID) -> list[UserRole]:
        return [r for r in self.items if r.user_id == user_id]

    async def lock_effective_holders(self, role_code: str, *, now: datetime) -> list[uuid.UUID]:
        return [r.user_id for r in self.items if r.role_code == role_code and r.is_effective(now)]

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        return [
            RoleGrant(r.role_code, r.scope_type, r.scope_id, r.expires_at)
            for r in self.items
            if r.user_id == user_id and r.is_effective(now)
        ]


class FakeCohortDirectory:
    """기수 → 과정 매핑 고정값. 조회 횟수를 센다."""

    def __init__(self, mapping: dict[uuid.UUID, uuid.UUID] | None = None) -> None:
        self.mapping = mapping or {}
        self.lookups = 0

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None:
        self.lookups += 1
        return self.mapping.get(cohort_id)


class CountingUserRoleRepository(InMemoryUserRoleRepository):
    def __init__(self) -> None:
        super().__init__()
        self.list_calls = 0

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        self.list_calls += 1
        return await super().list_grants(user_id, now=now)

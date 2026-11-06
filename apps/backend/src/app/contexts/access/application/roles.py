"""역할 시드·부여·조회 (공개 서비스)."""

import uuid

from app.contexts.access.domain.catalog import PERMISSIONS, ROLES
from app.contexts.access.domain.entities import RoleGrant, UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.domain.repositories import RoleCatalogRepository, UserRoleRepository
from app.core.clock import Clock


class RoleCatalogSeeder:
    """plan §2.3 권한표(access/domain/catalog.py)를 DB에 맞춘다. 멱등이다."""

    def __init__(self, catalog: RoleCatalogRepository) -> None:
        self._catalog = catalog

    async def seed(self) -> None:
        await self._catalog.sync(ROLES, PERMISSIONS)


class RoleAssignmentService:
    def __init__(self, user_roles: UserRoleRepository) -> None:
        self._user_roles = user_roles

    async def grant(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: RoleScopeType,
        scope_id: uuid.UUID | None = None,
    ) -> bool:
        """역할을 부여한다. 이미 있으면 아무것도 하지 않고 False.

        호출하는 쪽이 UnitOfWork를 연다.
        """
        user_role = UserRole(
            user_id=user_id, role_code=role_code, scope_type=scope_type, scope_id=scope_id
        )
        if await self._user_roles.exists(user_id, role_code, scope_type, scope_id):
            return False
        await self._user_roles.add(user_role)
        return True


class RoleQueries:
    def __init__(self, user_roles: UserRoleRepository, clock: Clock) -> None:
        self._user_roles = user_roles
        self._clock = clock

    async def list_for_user(self, user_id: uuid.UUID) -> list[RoleGrant]:
        return await self._user_roles.list_grants(user_id, now=self._clock.now())

"""access 리포지토리 구현 (Tortoise)."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from tortoise.expressions import Q

from app.contexts.access.domain.catalog import RoleDefinition
from app.contexts.access.domain.entities import RoleGrant, UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.models import PermissionModel, RoleModel, UserRoleModel
from app.shared.errors import ConflictError


class TortoiseRoleCatalogRepository:
    async def sync(self, roles: Sequence[RoleDefinition], permissions: dict[str, str]) -> None:
        """정의에 있는 역할·권한을 만들거나 고치고, 역할-권한 매핑을 정의와 같게 맞춘다.

        정의에서 빠진 역할·권한 행은 지우지 않는다 (부여 이력 보존). 매핑만 정리한다.
        """
        by_code: dict[str, PermissionModel] = {}
        for code, description in permissions.items():
            permission, _ = await PermissionModel.update_or_create(
                code=code, defaults={"description": description}
            )
            by_code[code] = permission

        for definition in roles:
            role, _ = await RoleModel.update_or_create(
                code=definition.code,
                defaults={"name": definition.name, "description": definition.description},
            )
            current = {p.code: p for p in await role.permissions.all()}
            missing = [by_code[c] for c in sorted(definition.permissions - current.keys())]
            extra = [p for c, p in current.items() if c not in definition.permissions]
            if missing:
                await role.permissions.add(*missing)
            if extra:
                await role.permissions.remove(*extra)


def _scope_filter(scope_id: uuid.UUID | None) -> Q:
    return Q(scope_id__isnull=True) if scope_id is None else Q(scope_id=scope_id)


class TortoiseUserRoleRepository:
    async def add(self, user_role: UserRole) -> None:
        role = await RoleModel.get_or_none(code=user_role.role_code)
        if role is None:
            raise ConflictError(
                "역할 정의가 없습니다. 역할 시드를 먼저 실행하세요.", code="role_not_seeded"
            )
        await UserRoleModel.create(
            id=user_role.id,
            role=role,
            user_id=user_role.user_id,
            scope_type=user_role.scope_type,
            scope_id=user_role.scope_id,
            expires_at=user_role.expires_at,
        )

    async def exists(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        return await UserRoleModel.filter(
            _scope_filter(scope_id),
            user_id=user_id,
            role__code=role_code,
            scope_type=scope_type,
        ).exists()

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        rows = (
            await UserRoleModel.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now), user_id=user_id
            )
            .select_related("role")
            .order_by("created_at", "id")
        )
        return [
            RoleGrant(
                role_code=row.role.code,
                scope_type=RoleScopeType(row.scope_type),
                scope_id=row.scope_id,
                expires_at=row.expires_at,
            )
            for row in rows
        ]

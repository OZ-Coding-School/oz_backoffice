"""access 리포지토리 구현 (Tortoise)."""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from tortoise.expressions import Q

from app.contexts.access.domain.catalog import (
    BUILTIN_ROLE_CODES,
    PERMISSIONS,
    ROLES,
    SUPER_ADMIN,
    RoleDefinition,
)
from app.contexts.access.domain.entities import RoleGrant, UserRole
from app.contexts.access.domain.enums import RoleScopeKind, RoleScopeType
from app.contexts.access.domain.roles import Role, builtin_scope_kind
from app.contexts.access.infrastructure.models import PermissionModel, RoleModel, UserRoleModel
from app.shared.errors import ConflictError


class TortoiseRoleCatalogRepository:
    async def sync(
        self,
        roles: Sequence[RoleDefinition],
        permissions: dict[str, str],
        legacy: Mapping[str, frozenset[str]] | None = None,
    ) -> None:
        """없는 권한·역할만 만들고, 새 역할에만 초기 권한 묶음을 넣는다 (A84).

        예전 권한 코드(`legacy`)를 가진 역할에는 대응하는 새 코드를 붙이고 예전 코드를 지운다(A86).
        정의에서 빠진 역할 행은 지우지 않는다 (부여 이력 보존).
        """
        by_code: dict[str, PermissionModel] = {}
        for code, description in permissions.items():
            permission, _ = await PermissionModel.update_or_create(
                code=code, defaults={"description": description}
            )
            by_code[code] = permission

        # 예전 코드 전환은 예전에만 있던 코드가 DB에 남아 있을 때 한 번만 한다. 새 목록에도 있는
        # 코드(예: mentoring.request.read)는 전환 뒤 화면에서 고친 값을 다시 덮지 않기 위해서다.
        retired = [code for code in (legacy or {}) if code not in permissions]
        if legacy and await PermissionModel.filter(code__in=retired).exists():
            for role in await RoleModel.filter(permissions__code__in=list(legacy)).distinct():
                held = await role.permissions.all()
                current = {p.code for p in held}
                wanted = set().union(*(legacy[c] for c in current if c in legacy)) - current
                if wanted:
                    await role.permissions.add(*[by_code[c] for c in sorted(wanted)])
                old = [p for p in held if p.code in retired]
                if old:
                    await role.permissions.remove(*old)
            await PermissionModel.filter(code__in=retired).delete()

        for definition in roles:
            role, created = await RoleModel.get_or_create(
                code=definition.code,
                defaults={"name": definition.name, "description": definition.description},
            )
            if definition.code == SUPER_ADMIN:
                wanted = set(by_code)  # 최고 관리자는 항상 모든 권한
            elif created:
                wanted = set(definition.permissions)
            else:
                continue
            current = {p.code for p in await role.permissions.all()}
            missing = [by_code[c] for c in sorted(wanted - current)]
            if missing:
                await role.permissions.add(*missing)


def _to_role(row: RoleModel) -> Role:
    return Role(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        scope_kind=(
            builtin_scope_kind(row.code)
            if row.code in BUILTIN_ROLE_CODES
            else RoleScopeKind(row.scope_kind or RoleScopeKind.SCOPED)
        ),
        permissions=frozenset(p.code for p in row.permissions),
    )


_BUILTIN_ORDER = {role.code: i for i, role in enumerate(ROLES)}


class TortoiseRoleRepository:
    async def list_all(self) -> list[Role]:
        rows = await RoleModel.all().prefetch_related("permissions").order_by("created_at", "id")
        roles = [_to_role(row) for row in rows]
        return sorted(roles, key=lambda r: _BUILTIN_ORDER.get(r.code, len(_BUILTIN_ORDER)))

    async def get(self, code: str) -> Role | None:
        row = await RoleModel.get_or_none(code=code).prefetch_related("permissions")
        return _to_role(row) if row else None

    async def lock(self, code: str) -> Role | None:
        row = await RoleModel.filter(code=code).select_for_update().first()
        if row is None:
            return None
        await row.fetch_related("permissions")
        return _to_role(row)

    async def name_taken(self, name: str, *, exclude_code: str | None = None) -> bool:
        query = RoleModel.filter(name=name)
        if exclude_code is not None:
            query = query.exclude(code=exclude_code)
        return await query.exists()

    async def add(self, role: Role) -> None:
        if await RoleModel.filter(code=role.code).exists():
            raise ConflictError("이미 있는 역할 코드입니다.", code="role_code_taken")
        await RoleModel.create(
            id=role.id,
            code=role.code,
            name=role.name,
            description=role.description,
            scope_kind=role.scope_kind,
        )

    async def save(self, role: Role) -> None:
        row = await RoleModel.get(code=role.code)
        row.name = role.name
        row.description = role.description  # type: ignore[assignment]  # null=True 필드 타입
        await row.save(update_fields=["name", "description"])
        current = {p.code: p for p in await row.permissions.all()}
        extra = [p for code, p in current.items() if code not in role.permissions]
        if extra:
            await row.permissions.remove(*extra)
        missing = sorted(role.permissions - current.keys())
        if missing:
            await row.permissions.add(*await PermissionModel.filter(code__in=missing))

    async def delete(self, code: str) -> None:
        row = await RoleModel.get(code=code)
        await row.permissions.clear()
        await row.delete()

    async def holder_counts(self) -> dict[str, int]:
        rows = await UserRoleModel.all().values("role__code", "user_id")
        holders: dict[str, set[object]] = {}
        for row in rows:
            holders.setdefault(row["role__code"], set()).add(row["user_id"])
        return {code: len(users) for code, users in holders.items()}


def _to_user_role(row: UserRoleModel) -> UserRole:
    return UserRole(
        id=row.id,
        user_id=row.user_id,  # type: ignore[attr-defined]  # Tortoise FK 컬럼 속성
        role_code=row.role.code,
        scope_type=RoleScopeType(row.scope_type),
        scope_id=row.scope_id,
        expires_at=row.expires_at,
    )


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

    async def remove(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> bool:
        role = await RoleModel.get_or_none(code=role_code)
        if role is None:
            return False
        deleted = await UserRoleModel.filter(
            _scope_filter(scope_id), user_id=user_id, role=role, scope_type=scope_type
        ).delete()
        return deleted > 0

    async def get(self, user_role_id: uuid.UUID) -> UserRole | None:
        row = await UserRoleModel.get_or_none(id=user_role_id).select_related("role")
        return _to_user_role(row) if row else None

    async def delete(self, user_role_id: uuid.UUID) -> None:
        await UserRoleModel.filter(id=user_role_id).delete()

    async def list_by_user(self, user_id: uuid.UUID) -> list[UserRole]:
        rows = (
            await UserRoleModel.filter(user_id=user_id)
            .select_related("role")
            .order_by("created_at", "id")
        )
        return [_to_user_role(row) for row in rows]

    async def lock_effective_holders(self, role_code: str, *, now: datetime) -> list[uuid.UUID]:
        rows = (
            await UserRoleModel.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now), role__code=role_code
            )
            .select_for_update()
            .values_list("user_id", flat=True)
        )
        return [uuid.UUID(str(user_id)) for user_id in rows]

    async def list_grants(self, user_id: uuid.UUID, *, now: datetime) -> list[RoleGrant]:
        rows = (
            await UserRoleModel.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now), user_id=user_id
            )
            .select_related("role")
            .prefetch_related("role__permissions")
            .order_by("created_at", "id")
        )
        return [
            RoleGrant(
                role_code=row.role.code,
                scope_type=RoleScopeType(row.scope_type),
                scope_id=row.scope_id,
                expires_at=row.expires_at,
                permissions=(
                    frozenset(PERMISSIONS)
                    if row.role.code == SUPER_ADMIN
                    else frozenset(p.code for p in row.role.permissions)
                ),
            )
            for row in rows
        ]

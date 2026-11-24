"""역할·권한 관리 (decisions A84, BE-3d). 권한: role.assign.

역할별 권한은 DB가 출처다. 최고 관리자는 항상 모든 권한이라 편집할 수 없고, 멘토·수강생은
소유 관계로 검사하므로 이 관리 대상에서 빠진다. 기본 역할은 지울 수 없고, 보유자가 있는 역할도
지울 수 없다.
"""

import uuid
from dataclasses import dataclass

from app.contexts.access.domain.catalog import GLOBAL_ONLY_PERMISSIONS, PERMISSIONS
from app.contexts.access.domain.enums import RoleScopeKind
from app.contexts.access.domain.repositories import RoleRepository
from app.contexts.access.domain.roles import Role
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError


@dataclass(frozen=True, slots=True)
class PermissionInfo:
    code: str
    description: str
    global_only: bool


@dataclass(frozen=True, slots=True)
class RoleSummary:
    role: Role
    holder_count: int


@dataclass(frozen=True, slots=True)
class RoleCatalogView:
    permissions: list[PermissionInfo]
    roles: list[RoleSummary]


def _snapshot(role: Role) -> dict[str, object]:
    return {
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "scope_kind": role.scope_kind.value,
        "permissions": sorted(role.permissions),
    }


class RoleCatalogAdministration:
    def __init__(self, *, roles: RoleRepository, audit: AuditRecorder, uow: UnitOfWork) -> None:
        self._roles = roles
        self._audit = audit
        self._uow = uow

    async def catalog(self) -> RoleCatalogView:
        counts = await self._roles.holder_counts()
        return RoleCatalogView(
            permissions=[
                PermissionInfo(code, description, code in GLOBAL_ONLY_PERMISSIONS)
                for code, description in PERMISSIONS.items()
            ],
            roles=[
                RoleSummary(role, counts.get(role.code, 0))
                for role in await self._roles.list_all()
                if not role.is_hidden
            ],
        )

    async def get(self, code: str) -> RoleSummary:
        role = await self._roles.get(code)
        if role is None or role.is_hidden:
            raise NotFoundError("역할을 찾을 수 없습니다.", code="role_not_found")
        counts = await self._roles.holder_counts()
        return RoleSummary(role, counts.get(code, 0))

    async def create(
        self,
        *,
        code: str,
        name: str,
        description: str | None,
        scope_kind: RoleScopeKind,
        actor_id: uuid.UUID,
    ) -> Role:
        role = Role.create(code=code, name=name, description=description, scope_kind=scope_kind)
        async with self._uow:
            if await self._roles.get(role.code) is not None:
                raise ConflictError("이미 있는 역할 코드입니다.", code="role_code_taken")
            if await self._roles.name_taken(role.name):
                raise ConflictError("이미 있는 역할 이름입니다.", code="role_name_taken")
            await self._roles.add(role)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role_definition.create",
                target_type="role",
                target_id=role.id,
                after=_snapshot(role),
            )
        return role

    async def update(
        self, code: str, *, name: str, description: str | None, actor_id: uuid.UUID
    ) -> Role:
        async with self._uow:
            role = await self._lock(code)
            before = _snapshot(role)
            role.rename(name=name, description=description)
            if await self._roles.name_taken(role.name, exclude_code=code):
                raise ConflictError("이미 있는 역할 이름입니다.", code="role_name_taken")
            await self._roles.save(role)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role_definition.update",
                target_type="role",
                target_id=role.id,
                before=before,
                after=_snapshot(role),
            )
        return role

    async def replace_permissions(
        self, code: str, permissions: list[str], *, actor_id: uuid.UUID
    ) -> Role:
        async with self._uow:
            role = await self._lock(code)
            before = _snapshot(role)
            role.replace_permissions(permissions)
            await self._roles.save(role)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role_definition.permissions",
                target_type="role",
                target_id=role.id,
                before=before,
                after=_snapshot(role),
            )
        return role

    async def delete(self, code: str, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            role = await self._lock(code)
            if role.is_builtin:
                raise BusinessRuleViolation("기본 역할은 지울 수 없습니다.", code="builtin_role")
            if (await self._roles.holder_counts()).get(code, 0) > 0:
                raise ConflictError(
                    "이 역할을 가진 회원이 있어 지울 수 없습니다. 먼저 회수해 주세요.",
                    code="role_in_use",
                )
            await self._roles.delete(code)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role_definition.delete",
                target_type="role",
                target_id=role.id,
                before=_snapshot(role),
            )

    async def _lock(self, code: str) -> Role:
        role = await self._roles.lock(code)
        if role is None or role.is_hidden:
            raise NotFoundError("역할을 찾을 수 없습니다.", code="role_not_found")
        return role

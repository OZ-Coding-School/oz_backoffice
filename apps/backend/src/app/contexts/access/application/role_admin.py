"""회원 역할 직접 관리 (decisions A17·A36·A85).

담당자·멘토 배정·수강 등록처럼 원천 테이블과 짝을 이루는 역할은 그 기능에서만 부여·회수한다
(D4: 담당자 표시와 권한이 어긋나지 않게). 이 서비스는 원천이 따로 없는 역할(최고 관리자·팀리드·
새 역할)만 다룬다. 새 과정·기수 범위 역할은 과정이나 기수를 골라 준다. 대상은 운영진 계정만이다.
마지막 최고 관리자는 회수할 수 없다 (관리자가 아무도 없는 상태 방지).
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.contexts.access.domain.catalog import SUPER_ADMIN
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.domain.repositories import RoleRepository, UserRoleRepository
from app.contexts.access.domain.roles import Role, is_directly_managed
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError


class UserDirectory(Protocol):
    """identity `UserQueries`가 구현."""

    async def get(self, user_id: uuid.UUID) -> User | None: ...


class ScopeTargets(Protocol):
    """academy `AcademyCatalog`가 구현 (과정·기수 존재 확인)."""

    async def get_bootcamp(self, bootcamp_id: uuid.UUID) -> object | None: ...
    async def get_cohort(self, cohort_id: uuid.UUID) -> object | None: ...


class RoleAdministration:
    def __init__(
        self,
        *,
        user_roles: UserRoleRepository,
        roles: RoleRepository,
        users: UserDirectory,
        scopes: ScopeTargets,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._user_roles = user_roles
        self._roles = roles
        self._users = users
        self._scopes = scopes
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserRole]:
        await self._get_user(user_id)
        return await self._user_roles.list_by_user(user_id)

    async def grant(
        self,
        user_id: uuid.UUID,
        role_code: str,
        *,
        actor_id: uuid.UUID,
        scope_type: RoleScopeType | None = None,
        scope_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
    ) -> UserRole:
        role = await self._directly_managed_role(role_code)
        scope_type = scope_type or RoleScopeType.GLOBAL
        if scope_type not in role.scopes or (scope_type is RoleScopeType.GLOBAL) != (
            scope_id is None
        ):
            raise BusinessRuleViolation(
                f"{role.name} 역할은 이 범위로 줄 수 없습니다.", code="invalid_role_scope"
            )
        now = self._clock.now()
        if expires_at is not None and expires_at <= now:
            raise BusinessRuleViolation(
                "만료 시각은 현재 이후여야 합니다.", code="invalid_expires_at"
            )
        await self._ensure_scope_exists(scope_type, scope_id)
        user = await self._get_user(user_id)
        if not user.is_approved or not user.can_login:
            raise BusinessRuleViolation(
                "승인된 활성 회원에게만 역할을 부여할 수 있습니다.", code="user_not_approved"
            )
        if user.account_type is not AccountType.STAFF:
            raise BusinessRuleViolation(
                "운영진 계정에게만 역할을 부여할 수 있습니다.", code="staff_only"
            )
        user_role = UserRole(
            user_id=user_id,
            role_code=role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            expires_at=expires_at,
        )
        async with self._uow:
            if await self._user_roles.exists(user_id, role_code, scope_type, scope_id):
                raise ConflictError("이미 가진 역할입니다.", code="role_already_granted")
            await self._user_roles.add(user_role)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role.grant",
                target_type="user",
                target_id=user_id,
                after={
                    "role": role_code,
                    "scope_type": scope_type.value,
                    "scope_id": str(scope_id) if scope_id else None,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )
        return user_role

    async def revoke(
        self, user_id: uuid.UUID, user_role_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        async with self._uow:
            user_role = await self._user_roles.get(user_role_id)
            if user_role is None or user_role.user_id != user_id:
                raise NotFoundError("역할 부여를 찾을 수 없습니다.", code="user_role_not_found")
            self._ensure_directly_managed(user_role.role_code)
            if user_role.role_code == SUPER_ADMIN and user_role.is_effective(self._clock.now()):
                holders = await self._user_roles.lock_effective_holders(
                    SUPER_ADMIN, now=self._clock.now()
                )
                if set(holders) == {user_id}:
                    raise ConflictError(
                        "마지막 최고 관리자는 회수할 수 없습니다.", code="last_super_admin"
                    )
            await self._user_roles.delete(user_role_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role.revoke",
                target_type="user",
                target_id=user_id,
                before={
                    "role": user_role.role_code,
                    "scope_type": user_role.scope_type.value,
                    "scope_id": str(user_role.scope_id) if user_role.scope_id else None,
                },
            )

    async def _get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("회원을 찾을 수 없습니다.", code="user_not_found")
        return user

    async def _directly_managed_role(self, role_code: str) -> Role:
        role = await self._roles.get(role_code)
        if role is None:
            raise BusinessRuleViolation("존재하지 않는 역할입니다.", code="role_not_found")
        self._ensure_directly_managed(role_code)
        return role

    async def _ensure_scope_exists(
        self, scope_type: RoleScopeType, scope_id: uuid.UUID | None
    ) -> None:
        if scope_id is None:
            return
        if (
            scope_type is RoleScopeType.BOOTCAMP
            and await self._scopes.get_bootcamp(scope_id) is None
        ):
            raise NotFoundError("과정을 찾을 수 없습니다.", code="bootcamp_not_found")
        if scope_type is RoleScopeType.COHORT and await self._scopes.get_cohort(scope_id) is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")

    @staticmethod
    def _ensure_directly_managed(role_code: str) -> None:
        if not is_directly_managed(role_code):
            raise BusinessRuleViolation(
                "이 역할은 담당자·멘토 배정이나 수강 등록에서 관리합니다.",
                code="role_managed_by_assignment",
            )

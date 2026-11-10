"""회원 역할 직접 관리 (decisions A17).

담당자·멘토 배정·수강 등록처럼 원천 테이블과 짝을 이루는 역할은 그 기능에서만 부여·회수한다
(D4: 담당자 표시와 권한이 어긋나지 않게). 이 서비스는 원천이 따로 없는 역할
(SUPER_ADMIN, TEAM_LEAD — A36)만 GLOBAL 범위로 다룬다.
마지막 최고 관리자는 회수할 수 없다 (관리자가 아무도 없는 상태 방지).
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.contexts.access.domain.catalog import ROLES_BY_CODE, SUPER_ADMIN, TEAM_LEAD
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.domain.repositories import UserRoleRepository
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError

DIRECTLY_MANAGED_ROLES = frozenset({SUPER_ADMIN, TEAM_LEAD})


class UserDirectory(Protocol):
    """identity `UserQueries`가 구현."""

    async def get(self, user_id: uuid.UUID) -> User | None: ...


class RoleAdministration:
    def __init__(
        self,
        *,
        user_roles: UserRoleRepository,
        users: UserDirectory,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._user_roles = user_roles
        self._users = users
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
        expires_at: datetime | None = None,
    ) -> UserRole:
        self._ensure_directly_managed(role_code)
        now = self._clock.now()
        if expires_at is not None and expires_at <= now:
            raise BusinessRuleViolation(
                "만료 시각은 현재 이후여야 합니다.", code="invalid_expires_at"
            )
        user = await self._get_user(user_id)
        if not user.is_approved or not user.can_login:
            raise BusinessRuleViolation(
                "승인된 활성 회원에게만 역할을 부여할 수 있습니다.", code="user_not_approved"
            )
        user_role = UserRole(
            user_id=user_id,
            role_code=role_code,
            scope_type=RoleScopeType.GLOBAL,
            expires_at=expires_at,
        )
        async with self._uow:
            if await self._user_roles.exists(user_id, role_code, RoleScopeType.GLOBAL, None):
                raise ConflictError("이미 가진 역할입니다.", code="role_already_granted")
            await self._user_roles.add(user_role)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.role.grant",
                target_type="user",
                target_id=user_id,
                after={
                    "role": role_code,
                    "scope_type": RoleScopeType.GLOBAL.value,
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
                before={"role": user_role.role_code, "scope_type": user_role.scope_type.value},
            )

    async def _get_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("회원을 찾을 수 없습니다.", code="user_not_found")
        return user

    @staticmethod
    def _ensure_directly_managed(role_code: str) -> None:
        if role_code not in ROLES_BY_CODE:
            raise BusinessRuleViolation("존재하지 않는 역할입니다.", code="role_not_found")
        if role_code not in DIRECTLY_MANAGED_ROLES:
            raise BusinessRuleViolation(
                "이 역할은 담당자·멘토 배정이나 수강 등록에서 관리합니다.",
                code="role_managed_by_assignment",
            )

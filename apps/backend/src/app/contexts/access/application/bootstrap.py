"""최고 관리자(SUPER_ADMIN) 등록 (decisions A12, CLI `create-super-admin`)."""

from dataclasses import dataclass

from app.contexts.access.application.roles import RoleAssignmentService, RoleCatalogSeeder
from app.contexts.access.domain.catalog import SUPER_ADMIN
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.domain.entities import User
from app.core.uow import UnitOfWork


@dataclass(frozen=True, slots=True)
class SuperAdminResult:
    user: User
    user_created: bool
    role_granted: bool


class SuperAdminBootstrap:
    """이메일로 최고 관리자를 등록한다.

    역할 정의를 먼저 맞추고(멱등), 운영진 회원을 승인 상태로 만든 뒤(없으면 생성)
    SUPER_ADMIN(GLOBAL)을 부여한다. 이미 최고 관리자면 바꾸지 않는다.
    """

    def __init__(
        self,
        *,
        seeder: RoleCatalogSeeder,
        users: UserAdministration,
        roles: RoleAssignmentService,
        audit: AuditRecorder,
        uow: UnitOfWork,
        staff_domain: str,
    ) -> None:
        self._seeder = seeder
        self._users = users
        self._roles = roles
        self._audit = audit
        self._uow = uow
        self._staff_domain = staff_domain

    async def run(self, email: str, *, name: str | None = None) -> SuperAdminResult:
        async with self._uow:
            await self._seeder.seed()
            user, created = await self._users.ensure_approved_staff(
                email, staff_domain=self._staff_domain, name=name
            )
            granted = await self._roles.grant(user.id, SUPER_ADMIN, RoleScopeType.GLOBAL)
            if granted:
                await self._audit.record(
                    actor_user_id=None,  # CLI(시스템) 작업
                    action="access.role.grant",
                    target_type="user",
                    target_id=user.id,
                    after={"role": SUPER_ADMIN, "scope_type": RoleScopeType.GLOBAL.value},
                )
        return SuperAdminResult(user=user, user_created=created, role_granted=granted)

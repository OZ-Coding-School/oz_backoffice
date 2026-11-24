"""최고 관리자(회원 필드) 등록 (decisions A12·A14·A87, CLI `create-super-admin`)."""

from dataclasses import dataclass

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.domain.entities import User
from app.core.uow import UnitOfWork


@dataclass(frozen=True, slots=True)
class SuperAdminResult:
    user: User
    user_created: bool
    role_granted: bool  # 이번에 최고 관리자가 됐는지


class SuperAdminBootstrap:
    """이메일로 최고 관리자를 등록한다.

    운영진 회원을 승인 상태로 만든 뒤(없으면 생성) 최고 관리자를 켠다.
    이미 최고 관리자면 바꾸지 않는다.
    """

    def __init__(
        self, *, users: UserAdministration, audit: AuditRecorder, uow: UnitOfWork, staff_domain: str
    ) -> None:
        self._users = users
        self._audit = audit
        self._uow = uow
        self._staff_domain = staff_domain

    async def run(self, email: str, *, name: str | None = None) -> SuperAdminResult:
        async with self._uow:
            user, created = await self._users.ensure_approved_staff(
                email, staff_domain=self._staff_domain, name=name
            )
            granted = not user.is_super_admin
            if granted:
                user = await self._users.set_super_admin(user.id, True)
                await self._audit.record(
                    actor_user_id=None,  # CLI(시스템) 작업
                    action="access.super_admin.enable",
                    target_type="user",
                    target_id=user.id,
                    after={"is_super_admin": True},
                )
        return SuperAdminResult(user=user, user_created=created, role_granted=granted)

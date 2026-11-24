"""최고 관리자 켜기·끄기 (decisions A87). 최고 관리자만 할 수 있고 마지막 1명은 끌 수 없다."""

import uuid

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.domain.entities import User
from app.core.uow import UnitOfWork


class SuperAdminAdministration:
    def __init__(self, *, users: UserAdministration, audit: AuditRecorder, uow: UnitOfWork) -> None:
        self._users = users
        self._audit = audit
        self._uow = uow

    async def set(self, user_id: uuid.UUID, enabled: bool, *, actor_id: uuid.UUID) -> User:
        async with self._uow:
            user = await self._users.set_super_admin(user_id, enabled)
            await self._audit.record(
                actor_user_id=actor_id,
                action="access.super_admin." + ("enable" if enabled else "disable"),
                target_type="user",
                target_id=user_id,
                after={"is_super_admin": enabled},
            )
        return user

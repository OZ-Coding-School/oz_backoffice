"""최고 관리자 켜기·끄기 API (PUT /admin/users/{user_id}/super-admin, decisions A87).

최고 관리자만 부를 수 있다(권한 코드가 아니라 회원 필드). 운영진 계정만 켤 수 있고(422 staff_only),
마지막 최고 관리자는 끌 수 없다(409 last_super_admin).
"""

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.contexts.access.application.super_admin import SuperAdminAdministration
from app.contexts.access.presentation.dependencies import SuperAdmin
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.user_admin import UserAdministration
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/admin/users/{user_id}/super-admin", tags=["admin-super-admin"])


class SuperAdminRequest(BaseModel):
    enabled: bool


class SuperAdminResponse(BaseModel):
    user_id: uuid.UUID
    is_super_admin: bool


def get_service(request: Request) -> SuperAdminAdministration:
    state = request.app.state
    return SuperAdminAdministration(
        users=cast("UserAdministration", state.user_admin),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
    )


@router.put("", response_model=SuperAdminResponse)
async def set_super_admin(
    user_id: uuid.UUID,
    body: SuperAdminRequest,
    admin: SuperAdmin,
    service: Annotated[SuperAdminAdministration, Depends(get_service)],
) -> SuperAdminResponse:
    user = await service.set(user_id, body.enabled, actor_id=admin.id)
    return SuperAdminResponse(user_id=user.id, is_super_admin=user.is_super_admin)

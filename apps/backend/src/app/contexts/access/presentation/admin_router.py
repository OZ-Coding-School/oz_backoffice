"""회원 역할 관리 API (/admin/users/{user_id}/roles). 권한: role.assign (전체 범위).

직접 부여·회수할 수 있는 역할은 최고 관리자·팀리드·새 역할이다 (decisions A17·A36·A85).
매니저·조교 역할은 담당자 API, 멘토·수강생 역할은 배정·가입 기능이 관리한다.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.application.role_admin import (
    RoleAdministration,
    ScopeTargets,
    UserDirectory,
)
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.domain.roles import is_directly_managed
from app.contexts.access.infrastructure.repositories import (
    TortoiseRoleRepository,
    TortoiseUserRoleRepository,
)
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/admin/users/{user_id}/roles", tags=["admin-user-roles"])


class UserRoleResponse(BaseModel):
    id: uuid.UUID
    role: str
    scope_type: RoleScopeType
    scope_id: uuid.UUID | None
    expires_at: datetime | None
    is_effective: bool
    managed_by: Literal["direct", "assignment"]  # assignment면 담당자·배정·가입 기능에서 관리


class GrantRoleRequest(BaseModel):
    role: str
    scope_type: RoleScopeType | None = Field(
        default=None, description="없으면 GLOBAL. 새 과정·기수 범위 역할은 BOOTCAMP·COHORT"
    )
    scope_id: uuid.UUID | None = Field(default=None, description="과정·기수 id (GLOBAL이면 없음)")
    expires_at: datetime | None = None  # 임시 권한 (예: 대리 확인)


def get_role_administration(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> RoleAdministration:
    state = request.app.state
    return RoleAdministration(
        user_roles=TortoiseUserRoleRepository(),
        roles=TortoiseRoleRepository(),
        users=cast("UserDirectory", state.user_queries),
        scopes=cast("ScopeTargets", state.academy_catalog),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


Admin = Annotated[User, Depends(require_permission("role.assign"))]
ServiceDep = Annotated[RoleAdministration, Depends(get_role_administration)]


def _response(user_role: UserRole, now: datetime) -> UserRoleResponse:
    return UserRoleResponse(
        id=user_role.id,
        role=user_role.role_code,
        scope_type=user_role.scope_type,
        scope_id=user_role.scope_id,
        expires_at=user_role.expires_at,
        is_effective=user_role.is_effective(now),
        managed_by="direct" if is_directly_managed(user_role.role_code) else "assignment",
    )


@router.get("", response_model=list[UserRoleResponse])
async def list_user_roles(
    user_id: uuid.UUID, _: Admin, service: ServiceDep, clock: Annotated[Clock, Depends(get_clock)]
) -> list[UserRoleResponse]:
    """회원의 모든 역할 (만료된 것 포함)."""
    now = clock.now()
    return [_response(r, now) for r in await service.list_for_user(user_id)]


@router.post("", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
async def grant_user_role(
    user_id: uuid.UUID,
    body: GrantRoleRequest,
    admin: Admin,
    service: ServiceDep,
    clock: Annotated[Clock, Depends(get_clock)],
) -> UserRoleResponse:
    """직접 관리 역할(최고 관리자·팀리드·새 역할)을 운영진 계정에 부여한다.

    다른 역할은 422 role_managed_by_assignment, 운영진이 아니면 422 staff_only,
    역할의 허용 범위와 다르면 422 invalid_role_scope.
    """
    user_role = await service.grant(
        user_id,
        body.role,
        actor_id=admin.id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        expires_at=body.expires_at,
    )
    return _response(user_role, clock.now())


@router.delete("/{user_role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_role(
    user_id: uuid.UUID, user_role_id: uuid.UUID, admin: Admin, service: ServiceDep
) -> Response:
    """직접 관리 역할을 회수한다. 마지막 최고 관리자는 409 last_super_admin."""
    await service.revoke(user_id, user_role_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

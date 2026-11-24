"""역할·권한 관리 API (/admin/roles, decisions A84). 권한: role.assign (전체 범위).

역할별 권한 표를 보고 고치며, 운영진 역할을 새로 만들고 지운다. 멘토·수강생은 나오지 않는다.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.application.role_catalog import (
    RoleCatalogAdministration,
    RoleSummary,
)
from app.contexts.access.domain.catalog import PERMISSIONS
from app.contexts.access.domain.enums import RoleScopeKind
from app.contexts.access.infrastructure.repositories import TortoiseRoleRepository
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/admin/roles", tags=["admin-roles"])


class PermissionDefinitionResponse(BaseModel):
    code: str
    description: str
    global_only: bool = Field(description="전체 범위 역할에만 켤 수 있음")


class RoleDefinitionResponse(BaseModel):
    code: str
    name: str
    description: str | None
    scope_kind: RoleScopeKind = Field(description="GLOBAL = 전체, SCOPED = 과정·기수")
    builtin: bool = Field(description="기본 역할 (지울 수 없음)")
    permissions_editable: bool = Field(description="false면 최고 관리자 (항상 모든 권한)")
    permissions: list[str] = Field(description="권한 코드, 권한 정의 순서")
    holder_count: int = Field(description="부여받은 회원 수 (만료 포함)")


class RoleCatalogResponse(BaseModel):
    permissions: list[PermissionDefinitionResponse]
    roles: list[RoleDefinitionResponse] = Field(description="기본 역할 → 새 역할(만든 순서)")


class CreateRoleRequest(BaseModel):
    code: str = Field(description="영문 대문자로 시작, 대문자·숫자·밑줄 2~50자")
    name: str
    description: str | None = None
    scope_kind: RoleScopeKind


class UpdateRoleRequest(BaseModel):
    name: str
    description: str | None = None


class ReplacePermissionsRequest(BaseModel):
    permissions: list[str]


def get_role_catalog_administration(request: Request) -> RoleCatalogAdministration:
    return RoleCatalogAdministration(
        roles=TortoiseRoleRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )


Admin = Annotated[User, Depends(require_permission("role.assign"))]
ServiceDep = Annotated[RoleCatalogAdministration, Depends(get_role_catalog_administration)]

_ORDER = {code: i for i, code in enumerate(PERMISSIONS)}


def _response(summary: RoleSummary) -> RoleDefinitionResponse:
    role = summary.role
    return RoleDefinitionResponse(
        code=role.code,
        name=role.name,
        description=role.description,
        scope_kind=role.scope_kind,
        builtin=role.is_builtin,
        permissions_editable=not role.permissions_locked,
        permissions=sorted(role.effective_permissions, key=lambda c: _ORDER.get(c, len(_ORDER))),
        holder_count=summary.holder_count,
    )


@router.get("", response_model=RoleCatalogResponse)
async def role_catalog(_: Admin, service: ServiceDep) -> RoleCatalogResponse:
    view = await service.catalog()
    return RoleCatalogResponse(
        permissions=[
            PermissionDefinitionResponse(
                code=p.code, description=p.description, global_only=p.global_only
            )
            for p in view.permissions
        ],
        roles=[_response(r) for r in view.roles],
    )


@router.post("", response_model=RoleDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: CreateRoleRequest, admin: Admin, service: ServiceDep
) -> RoleDefinitionResponse:
    """새 역할 (권한 없음). 코드·이름 중복은 409 role_code_taken·role_name_taken."""
    role = await service.create(
        code=body.code,
        name=body.name,
        description=body.description,
        scope_kind=body.scope_kind,
        actor_id=admin.id,
    )
    return _response(await service.get(role.code))


@router.patch("/{code}", response_model=RoleDefinitionResponse)
async def update_role(
    code: str, body: UpdateRoleRequest, admin: Admin, service: ServiceDep
) -> RoleDefinitionResponse:
    await service.update(code, name=body.name, description=body.description, actor_id=admin.id)
    return _response(await service.get(code))


@router.put("/{code}/permissions", response_model=RoleDefinitionResponse)
async def replace_role_permissions(
    code: str, body: ReplacePermissionsRequest, admin: Admin, service: ServiceDep
) -> RoleDefinitionResponse:
    """권한 묶음 교체. 최고 관리자는 422 role_permissions_locked,
    과정·기수 범위 역할에 전체 전용 권한은 422 global_only_permission."""
    await service.replace_permissions(code, body.permissions, actor_id=admin.id)
    return _response(await service.get(code))


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(code: str, admin: Admin, service: ServiceDep) -> Response:
    """기본 역할은 422 builtin_role, 보유자가 있으면 409 role_in_use."""
    await service.delete(code, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

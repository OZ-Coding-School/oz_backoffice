"""역할 보유자 목록 API (/admin/role-holders, decisions A85). 권한: role.assign."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.contexts.access.application.role_holders import (
    HolderAffiliations,
    HolderUsers,
    RoleHolder,
    RoleHolderQueries,
    ScopeNames,
)
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import (
    TortoiseRoleRepository,
    TortoiseUserRoleRepository,
)
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.pagination import Page

router = APIRouter(prefix="/admin/role-holders", tags=["admin-role-holders"])


class HolderRoleResponse(BaseModel):
    id: uuid.UUID = Field(description="역할 부여 id (회수할 때 씀)")
    role: str
    role_name: str
    scope_type: RoleScopeType
    scope_id: uuid.UUID | None
    bootcamp_name: str | None = Field(description="과정·기수 범위면 과정명")
    cohort_number: int | None = Field(description="기수 범위면 기수 번호")
    expires_at: datetime | None
    is_effective: bool = Field(description="false면 만료")
    managed_by: Literal["direct", "assignment"] = Field(
        description="direct = 이 화면에서 회수, assignment = 담당자 배정에서 관리"
    )


class RoleHolderResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    department_name: str | None
    team_name: str | None
    position_name: str | None
    roles: list[HolderRoleResponse]

    @classmethod
    def of(cls, holder: RoleHolder) -> "RoleHolderResponse":
        a = holder.affiliation
        return cls(
            user_id=holder.user.id,
            name=holder.user.name,
            email=holder.user.email,
            department_name=a.department_name if a else None,
            team_name=a.team_name if a else None,
            position_name=a.position_name if a else None,
            roles=[
                HolderRoleResponse(
                    id=r.user_role.id,
                    role=r.user_role.role_code,
                    role_name=r.role_name,
                    scope_type=r.user_role.scope_type,
                    scope_id=r.user_role.scope_id,
                    bootcamp_name=r.bootcamp_name,
                    cohort_number=r.cohort_number,
                    expires_at=r.user_role.expires_at,
                    is_effective=r.is_effective,
                    managed_by=r.managed_by,
                )
                for r in holder.roles
            ],
        )


def get_role_holder_queries(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> RoleHolderQueries:
    state = request.app.state
    return RoleHolderQueries(
        user_roles=TortoiseUserRoleRepository(),
        roles=TortoiseRoleRepository(),
        users=cast("HolderUsers", state.user_queries),
        affiliations=cast("HolderAffiliations", state.employee_queries),
        scopes=cast("ScopeNames", state.academy_catalog),
        clock=clock,
    )


Admin = Annotated[User, Depends(require_permission("role.assign"))]


@router.get("", response_model=Page[RoleHolderResponse])
async def list_role_holders(
    _: Admin,
    queries: Annotated[RoleHolderQueries, Depends(get_role_holder_queries)],
    role: Annotated[str | None, Query(max_length=50, description="이 역할을 가진 사람만")] = None,
    q: Annotated[str | None, Query(max_length=50, description="이름·이메일")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RoleHolderResponse]:
    """멘토·수강생을 뺀 역할 보유자 (사람 단위, 이름순, 만료된 부여 포함)."""
    holders, total = await queries.list(role_code=role, query=q, limit=limit, offset=offset)
    return Page(
        items=[RoleHolderResponse.of(h) for h in holders], total=total, limit=limit, offset=offset
    )

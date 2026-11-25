"""전체 회원 API (/admin/users, decisions A94).

승인된 계정만 보이고, 비활성화는 로그인을 막고 refresh 토큰을 모두 폐기한다.
"""

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.application.member_admin import (
    REASON_MAX_LENGTH,
    AuditReader,
    MemberAdministration,
    MemberDetail,
    MemberLinksReader,
)
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.identity.presentation.dependencies import TokensDep
from app.core.pagination import Page
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/admin/users", tags=["admin-members"])

Reader = Annotated[User, Depends(require_permission("member.user.read"))]
Manager = Annotated[User, Depends(require_permission("member.user.manage"))]


def get_member_admin(request: Request) -> MemberAdministration:
    state = request.app.state
    return MemberAdministration(
        users=TortoiseUserRepository(),
        links=cast("MemberLinksReader", state.member_links),
        audit=cast("AuditRecorder", state.audit_recorder),
        audit_reader=cast("AuditReader", state.audit_queries),
        uow=UnitOfWork(),
    )


ServiceDep = Annotated[MemberAdministration, Depends(get_member_admin)]


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


class MemberResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone_number: str | None
    account_type: AccountType
    is_active: bool
    is_super_admin: bool
    approved_at: datetime | None
    last_login_at: datetime | None

    @classmethod
    def of(cls, u: User) -> "MemberResponse":
        return cls(
            id=u.id,
            name=u.name,
            email=u.email,
            phone_number=u.phone_number,
            account_type=u.account_type,
            is_active=u.is_active,
            is_super_admin=u.is_super_admin,
            approved_at=u.approved_at,
            last_login_at=u.last_login_at,
        )


class MemberCounts(BaseModel):
    ALL: int
    STUDENT: int
    MENTOR: int
    STAFF: int


class MemberPage(Page[MemberResponse]):
    counts: MemberCounts = Field(description="종류별 수 (검색·상태 필터를 따름, 종류 필터는 무시)")


class EnrollmentLink(BaseModel):
    bootcamp_name: str
    cohort_number: int
    status: str = Field(
        description="수강 상태 (ENROLLED·COMPLETED·DROPPED·EARLY_EMPLOYED·TRANSFERRED)"
    )


class AssignmentLink(BaseModel):
    bootcamp_name: str
    cohort_number: int
    active: bool


class MemberEventResponse(BaseModel):
    action: Literal["DEACTIVATE", "ACTIVATE"]
    reason: str | None
    actor_name: str | None
    at: datetime


class MemberDetailResponse(MemberResponse):
    enrollments: list[EnrollmentLink] = Field(description="수강생: 수강 기수 (최근 시작순)")
    assignments: list[AssignmentLink] = Field(description="멘토: 배정 기수 (활성 먼저)")
    contract_count: int | None = Field(description="멘토: 계약 수")
    department_name: str | None = Field(description="운영진: 부서")
    team_name: str | None = Field(description="운영진: 팀")
    position_name: str | None = Field(description="운영진: 직위")
    history: list[MemberEventResponse] = Field(description="비활성화·활성화 이력 (최신순)")


class DeactivateRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)


class ActivateRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)


async def _detail(d: MemberDetail, users: UserQueries) -> MemberDetailResponse:
    actors = await users.get_many([e.actor_user_id for e in d.history if e.actor_user_id])
    base = MemberResponse.of(d.user).model_dump()
    return MemberDetailResponse(
        **base,
        enrollments=[EnrollmentLink(**asdict(e)) for e in d.links.enrollments],
        assignments=[AssignmentLink(**asdict(a)) for a in d.links.assignments],
        contract_count=d.links.contract_count,
        department_name=d.links.department_name,
        team_name=d.links.team_name,
        position_name=d.links.position_name,
        history=[
            MemberEventResponse(
                action="DEACTIVATE" if e.deactivated else "ACTIVATE",
                reason=e.reason,
                actor_name=(a.name if (a := actors.get(e.actor_user_id)) else None)
                if e.actor_user_id
                else None,
                at=e.at,
            )
            for e in d.history
        ],
    )


@router.get("", response_model=MemberPage)
async def list_members(
    _: Reader,
    service: ServiceDep,
    account_type: AccountType | None = None,
    q: Annotated[str | None, Query(max_length=50, description="이름·이메일·휴대폰")] = None,
    status: Literal["active", "inactive"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemberPage:
    """승인된 계정(탈퇴 제외), 승인 최신순 (A94)."""
    active = None if status is None else status == "active"
    users, total, counts = await service.search(
        account_type=account_type, query=q, active=active, limit=limit, offset=offset
    )
    return MemberPage(
        items=[MemberResponse.of(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
        counts=MemberCounts(
            ALL=sum(counts.values()),
            STUDENT=counts.get(AccountType.STUDENT, 0),
            MENTOR=counts.get(AccountType.MENTOR, 0),
            STAFF=counts.get(AccountType.STAFF, 0),
        ),
    )


UsersDep = Annotated[UserQueries, Depends(get_user_queries)]


@router.get("/{user_id}", response_model=MemberDetailResponse)
async def get_member(
    user_id: uuid.UUID, _: Reader, service: ServiceDep, users: UsersDep
) -> MemberDetailResponse:
    """계정 정보 + 종류별 연결 정보 + 비활성화·활성화 이력 (A94)."""
    return await _detail(await service.detail(user_id), users)


@router.post("/{user_id}/deactivate", response_model=MemberDetailResponse)
async def deactivate_member(
    user_id: uuid.UUID,
    body: DeactivateRequest,
    admin: Manager,
    service: ServiceDep,
    users: UsersDep,
    tokens: TokensDep,
) -> MemberDetailResponse:
    """로그인을 막고 refresh 토큰을 모두 폐기한다. 자기 자신·마지막 최고 관리자는 409."""
    await service.deactivate(user_id, body.reason, actor_id=admin.id, sessions=tokens)
    return await _detail(await service.detail(user_id), users)


@router.post("/{user_id}/activate", response_model=MemberDetailResponse)
async def activate_member(
    user_id: uuid.UUID, body: ActivateRequest, admin: Manager, service: ServiceDep, users: UsersDep
) -> MemberDetailResponse:
    await service.activate(user_id, body.reason, actor_id=admin.id)
    return await _detail(await service.detail(user_id), users)

"""수강생·멘토 가입 승인 관리 API (decisions A33).

운영진 (`user.approve`, 담당 범위는 서비스에서 판정):
GET  /admin/approvals                          → 승인 대기 목록 (수강생: 담당 기수, 멘토: 계약 권한)
POST /admin/approvals/{user_id}/approve        → 수강생은 student_id, 멘토는 contract_ids(0건 이상)
POST /admin/approvals/{user_id}/reject         → 사유 필수

신청자 본인:
GET  /me/member-signup                         → 최근 신청 (상태, 반려 사유)
POST /me/member-signup                         → 반려 후 재신청 (자동 매칭 다시)
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.access.presentation.dependencies import (
    CurrentUser,
    PermissionCheckerDep,
    require_permission,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.application.signup import MailDispatcher
from app.contexts.identity.application.signup_matching import (
    RoleGranter,
    SignupMatcher,
)
from app.contexts.identity.application.signup_review import (
    MemberSignupSelfService,
    MentorApprover,
    ResubmitForm,
    SignupReviewService,
    SignupView,
    StudentSelector,
)
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import (
    MemberSignupStatus,
    MemberSignupType,
    SignupMatchResult,
    UserApprovalStatus,
)
from app.contexts.identity.domain.signup import MemberSignup
from app.contexts.identity.infrastructure.repositories import (
    TortoiseMemberSignupRepository,
    TortoiseUserRepository,
)
from app.contexts.identity.presentation.dependencies import ClockDep, SettingsDep
from app.contexts.identity.presentation.signup_router import get_academy_catalog
from app.core.pagination import Page
from app.core.uow import UnitOfWork

admin_router = APIRouter(prefix="/admin/approvals", tags=["admin-approvals"])
me_router = APIRouter(prefix="/me/member-signup", tags=["member-signup"])

Approver = Annotated[User, Depends(require_permission("user.approve", any_scope=True))]


def _login_url(settings: Any) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/login"


def get_review_service(
    request: Request, settings: SettingsDep, clock: ClockDep, checker: PermissionCheckerDep
) -> SignupReviewService:
    state = request.app.state
    return SignupReviewService(
        users=TortoiseUserRepository(),
        signups=TortoiseMemberSignupRepository(),
        permissions=checker,
        students=cast("StudentSelector", state.student_claims),
        mentors=cast("MentorApprover", state.mentor_onboarding),
        roles=cast("RoleGranter", state.role_assignments),
        dispatcher=cast("MailDispatcher", state.mail_dispatcher),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        sender_name=settings.mail_sender_name,
        login_url=_login_url(settings),
    )


def get_self_service(
    request: Request,
    settings: SettingsDep,
    clock: ClockDep,
    catalog: Annotated[AcademyCatalog, Depends(get_academy_catalog)],
) -> MemberSignupSelfService:
    state = request.app.state
    return MemberSignupSelfService(
        users=TortoiseUserRepository(),
        signups=TortoiseMemberSignupRepository(),
        cohorts=catalog,
        matcher=cast("SignupMatcher", state.signup_matcher),
        dispatcher=cast("MailDispatcher", state.mail_dispatcher),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        sender_name=settings.mail_sender_name,
        login_url=_login_url(settings),
    )


ReviewDep = Annotated[SignupReviewService, Depends(get_review_service)]
SelfDep = Annotated[MemberSignupSelfService, Depends(get_self_service)]


# ---------------------------------------------------------------- 스키마
class MemberSignupResponse(BaseModel):
    id: uuid.UUID
    signup_type: MemberSignupType
    status: MemberSignupStatus
    requested_cohort_id: uuid.UUID | None
    nickname: str | None
    display_name_preference: DisplayNamePreference | None
    match_result: SignupMatchResult | None
    reject_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime | None

    @classmethod
    def of(cls, signup: MemberSignup) -> "MemberSignupResponse":
        return cls(
            id=signup.id,
            signup_type=signup.signup_type,
            status=signup.status,
            requested_cohort_id=signup.requested_cohort_id,
            nickname=signup.nickname,
            display_name_preference=signup.display_name_preference,
            match_result=signup.match_result,
            reject_reason=signup.reject_reason,
            reviewed_at=signup.reviewed_at,
            created_at=signup.created_at,
        )


class ApplicantResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    phone_number: str | None
    approval_status: UserApprovalStatus
    signup: MemberSignupResponse

    @classmethod
    def of(cls, view: SignupView) -> "ApplicantResponse":
        return cls(
            user_id=view.user.id,
            name=view.user.name,
            email=view.user.email,
            phone_number=view.user.phone_number,
            approval_status=view.user.approval_status,
            signup=MemberSignupResponse.of(view.signup),
        )


class ApproveRequest(BaseModel):
    student_id: uuid.UUID | None = Field(default=None, description="수강생 승인: 연결할 명단")
    contract_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=50, description="멘토 승인: 연결할 계약 (0건 이상)"
    )


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class ResubmitRequest(BaseModel):
    signup_type: MemberSignupType
    cohort_id: uuid.UUID | None = None
    nickname: str | None = Field(default=None, max_length=30)
    display_name_preference: DisplayNamePreference | None = None


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[ApplicantResponse])
async def list_pending(
    user: Approver,
    review: ReviewDep,
    signup_type: MemberSignupType | None = None,
    cohort_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ApplicantResponse]:
    """오래된 신청부터. 담당 범위 밖의 신청은 보이지 않는다."""
    views, total = await review.list_pending(
        user.id, signup_type=signup_type, cohort_id=cohort_id, limit=limit, offset=offset
    )
    return Page(
        items=[ApplicantResponse.of(v) for v in views], total=total, limit=limit, offset=offset
    )


@admin_router.post("/{user_id}/approve", response_model=ApplicantResponse)
async def approve(
    user_id: uuid.UUID, body: ApproveRequest, user: Approver, review: ReviewDep
) -> ApplicantResponse:
    if body.student_id is not None:
        view = await review.approve_student(user_id, student_id=body.student_id, actor_id=user.id)
    else:
        view = await review.approve_mentor(
            user_id, contract_ids=body.contract_ids, actor_id=user.id
        )
    return ApplicantResponse.of(view)


@admin_router.post("/{user_id}/reject", response_model=ApplicantResponse)
async def reject(
    user_id: uuid.UUID, body: RejectRequest, user: Approver, review: ReviewDep
) -> ApplicantResponse:
    return ApplicantResponse.of(await review.reject(user_id, reason=body.reason, actor_id=user.id))


# ---------------------------------------------------------------- 신청자 본인
@me_router.get("", response_model=MemberSignupResponse)
async def my_signup(user: CurrentUser, service: SelfDep) -> MemberSignupResponse:
    return MemberSignupResponse.of(await service.latest(user.id))


@me_router.post("", response_model=ApplicantResponse, status_code=status.HTTP_201_CREATED)
async def resubmit(body: ResubmitRequest, user: CurrentUser, service: SelfDep) -> ApplicantResponse:
    view = await service.resubmit(
        user.id,
        ResubmitForm(
            signup_type=body.signup_type,
            cohort_id=body.cohort_id,
            nickname=body.nickname,
            display_name_preference=body.display_name_preference,
        ),
    )
    return ApplicantResponse.of(view)

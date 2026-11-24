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
from datetime import date, datetime
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
    SignupMatcher,
)
from app.contexts.identity.application.signup_review import (
    CohortScopeCatalog,
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

Approver = Annotated[User, Depends(require_permission("member.approval.manage", any_scope=True))]
ApproverReader = Annotated[
    User, Depends(require_permission("member.approval.read", any_scope=True))
]


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
    requested_bootcamp_name: str | None = Field(default=None, description="신청 기수 과정명 (A82)")
    requested_cohort_number: int | None = Field(default=None, description="신청 기수 번호 (A82)")

    @classmethod
    def of(cls, view: SignupView, label: tuple[str, int] | None = None) -> "ApplicantResponse":
        return cls(
            user_id=view.user.id,
            name=view.user.name,
            email=view.user.email,
            phone_number=view.user.phone_number,
            approval_status=view.user.approval_status,
            signup=MemberSignupResponse.of(view.signup),
            requested_bootcamp_name=label[0] if label else None,
            requested_cohort_number=label[1] if label else None,
        )


class StudentCandidateResponse(BaseModel):
    student_id: uuid.UUID
    name: str
    phone_number: str | None
    cohort_id: uuid.UUID
    bootcamp_name: str | None
    cohort_number: int | None
    enrollment_status: str
    name_match: bool
    phone_match: bool
    same_cohort: bool = Field(description="신청 기수의 명단")


class ContractCandidateResponse(BaseModel):
    contract_id: uuid.UUID
    contractor_name: str
    contractor_phone: str | None
    title: str
    status: str
    start_date: date
    end_date: date
    name_match: bool
    phone_match: bool


class CandidatesResponse(BaseModel):
    signup_type: MemberSignupType
    students: list[StudentCandidateResponse] = Field(description="수강생 신청: 연결할 명단 후보")
    contracts: list[ContractCandidateResponse] = Field(description="멘토 신청: 연결할 계약 후보")


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
    user: ApproverReader,
    review: ReviewDep,
    catalog: Annotated[AcademyCatalog, Depends(get_academy_catalog)],
    signup_type: MemberSignupType | None = None,
    cohort_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ApplicantResponse]:
    """오래된 신청부터. 담당 범위 밖의 신청은 보이지 않는다."""
    views, total = await review.list_pending(
        user.id, signup_type=signup_type, cohort_id=cohort_id, limit=limit, offset=offset
    )
    labels = await catalog.cohort_labels(
        {v.signup.requested_cohort_id for v in views if v.signup.requested_cohort_id}
    )

    def label(view: SignupView) -> tuple[str, int] | None:
        found = (
            labels.get(view.signup.requested_cohort_id) if view.signup.requested_cohort_id else None
        )
        return (found.bootcamp_name, found.cohort_number) if found else None

    return Page(
        items=[ApplicantResponse.of(v, label(v)) for v in views],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_router.get("/{user_id}/candidates", response_model=CandidatesResponse)
async def candidates(
    user_id: uuid.UUID,
    user: ApproverReader,
    review: ReviewDep,
    catalog: Annotated[AcademyCatalog, Depends(get_academy_catalog)],
    q: Annotated[str | None, Query(max_length=50, description="이름·휴대폰")] = None,
) -> CandidatesResponse:
    """수동 승인 후보 (A82). q가 없으면 이름 또는 휴대폰이 같은 것, 최대 20개."""
    found = await review.candidates(
        user_id, actor_id=user.id, query=q, cohorts=cast("CohortScopeCatalog", catalog)
    )
    labels = await catalog.cohort_labels({s.candidate.cohort_id for s in found.students})
    return CandidatesResponse(
        signup_type=found.signup_type,
        students=[
            StudentCandidateResponse(
                student_id=s.candidate.student_id,
                name=s.candidate.name,
                phone_number=s.candidate.phone_number,
                cohort_id=s.candidate.cohort_id,
                bootcamp_name=labels[s.candidate.cohort_id].bootcamp_name
                if s.candidate.cohort_id in labels
                else None,
                cohort_number=labels[s.candidate.cohort_id].cohort_number
                if s.candidate.cohort_id in labels
                else None,
                enrollment_status=s.candidate.status,
                name_match=s.name_match,
                phone_match=s.phone_match,
                same_cohort=s.same_cohort,
            )
            for s in found.students
        ],
        contracts=[
            ContractCandidateResponse(
                contract_id=c.candidate.contract_id,
                contractor_name=c.candidate.contractor_name,
                contractor_phone=c.candidate.contractor_phone,
                title=c.candidate.title,
                status=c.candidate.status,
                start_date=c.candidate.start_date,
                end_date=c.candidate.end_date,
                name_match=c.name_match,
                phone_match=c.phone_match,
            )
            for c in found.contracts
        ],
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

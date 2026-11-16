"""멘토링 신청 API (decisions A42, P11-1: 신청·승인 전 취소·조회).

수강생(승인된 회원):
  POST /mentoring/requests                    1:1(cohort_id·mentor_id) 또는 팀(team_id) 신청
  POST /mentoring/requests/{id}/cancel        취소 (사유 필수): 대기는 신청자, 승인 후는 신청자·담당
                                              멘토가 시작 min_lead_hours 전까지 (M26)
  POST /mentoring/requests/{id}/change        변경: 같은 대상으로 기존 취소 + 새 신청 (A44)
  GET  /me/mentoring/requests?status=         본인 1:1 + 소속 팀 신청
멘토:
  GET  /me/mentor-requests?status=            받은 신청
  POST /mentoring/requests/{id}/approve       희망 일시 하나를 골라 승인 → 세션 생성 (A43)
  POST /mentoring/requests/{id}/reject        반려 (사유 필수)
운영진 (기수 범위):
  GET  /admin/cohorts/{cohort_id}/mentoring/requests?status=&mentor_id=   mentoring.request.read
  POST /admin/cohorts/{cohort_id}/mentoring/requests/{id}/cancel          mentoring.request.cancel
       {reason, refund}: 마감과 무관, 대기는 보류 해제, 승인은 예정 세션만·환불 선택 (A44)
"""

import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime, BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.approval_service import MentoringApprovalService
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.meet_service import MeetSpaceScheduler
from app.contexts.mentoring.application.request_service import (
    ChangeInput,
    MentoringRequestService,
    RequestInput,
    StudentLookup,
)
from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.contexts.mentoring.domain.request import (
    DETAIL_MAX_LENGTH,
    MAX_DESIRED,
    MAX_DURATION_MINUTES,
    REASON_MAX_LENGTH,
    TOPIC_MAX_LENGTH,
    MentoringRequest,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.contexts.mentoring.presentation.availability_router import get_available_times_service
from app.contexts.mentoring.presentation.notices import build_notices
from app.contexts.mentoring.presentation.presenters import NameBook
from app.contexts.mentoring.presentation.session_router import SessionPresenter, SessionResponse
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.pagination import Page
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/mentoring/requests", tags=["mentoring-requests"])
me_router = APIRouter(prefix="/me", tags=["mentoring-requests"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/requests", tags=["admin-mentoring-requests"]
)

RequestReader = Annotated[
    User, Depends(require_permission("mentoring.request.read", cohort_param="cohort_id"))
]
RequestCanceler = Annotated[
    User, Depends(require_permission("mentoring.request.cancel", cohort_param="cohort_id"))
]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def get_request_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentoringRequestService:
    state = request.app.state
    return MentoringRequestService(
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        teams=TortoiseMentoringTeamRepository(),
        settings=TortoiseCohortMentoringSettingsRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        availability=get_available_times_service(request, clock),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        notices=build_notices(request, clock),
    )


ServiceDep = Annotated[MentoringRequestService, Depends(get_request_service)]


def get_approval_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentoringApprovalService:
    state = request.app.state
    return MentoringApprovalService(
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        teams=TortoiseMentoringTeamRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        users=cast("UserQueries", state.user_queries),
        meet=cast("MeetSpaceScheduler", state.meet_scheduler),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        notices=build_notices(request, clock),
    )


ApprovalDep = Annotated[MentoringApprovalService, Depends(get_approval_service)]


# ---------------------------------------------------------------- 스키마
class RequestCreate(BaseModel):
    """1:1은 cohort_id·mentor_id, 팀은 team_id(담당 멘토에게 자동)."""

    cohort_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    topic: str = Field(min_length=1, max_length=TOPIC_MAX_LENGTH)
    detail: str = Field(min_length=1, max_length=DETAIL_MAX_LENGTH)
    desired_times: list[AwareDatetime] = Field(
        min_length=1, max_length=MAX_DESIRED, description="1~3순위 시작 일시 (정각·30분)"
    )
    duration: int = Field(gt=0, le=MAX_DURATION_MINUTES, description="분, 진행 단위의 배수")


class CancelBody(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)


class ChangeBody(BaseModel):
    """같은 멘토·같은 방식(1:1/팀)에서 내용만 바꾼다."""

    topic: str = Field(min_length=1, max_length=TOPIC_MAX_LENGTH)
    detail: str = Field(min_length=1, max_length=DETAIL_MAX_LENGTH)
    desired_times: list[AwareDatetime] = Field(min_length=1, max_length=MAX_DESIRED)
    duration: int = Field(gt=0, le=MAX_DURATION_MINUTES)


class StaffCancelBody(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)
    refund: bool = Field(default=True, description="승인된 신청만 적용 (대기 신청은 항상 해제)")


class ApproveBody(BaseModel):
    starts_at: AwareDatetime = Field(description="희망 일시 중 하나")


class RequestResponse(BaseModel):
    id: uuid.UUID
    status: MentoringRequestStatus
    team_id: uuid.UUID | None = Field(description="없으면 1:1")
    team_label: str | None
    requester_id: uuid.UUID = Field(description="신청한 수강 등록")
    requester_name: str
    mentor_id: uuid.UUID
    mentor_display_name: str
    topic: str
    detail: str
    desired_times: list[datetime]
    duration: int
    reject_reason: str | None
    rejected_at: datetime | None
    cancel_reason: str | None
    canceled_at: datetime | None
    replaced_request_id: uuid.UUID | None
    created_at: datetime | None


class AdminRequestResponse(RequestResponse):
    mentor_name: str = Field(description="멘토 실명 (운영진 응답에만)")


class ApprovalResponse(BaseModel):
    request: RequestResponse
    session: SessionResponse


class Presenter:
    def __init__(self, request: Request) -> None:
        self._names = NameBook(request)

    async def admin(self, items: list[MentoringRequest]) -> list[AdminRequestResponse]:
        names = await self._names.of(items)
        return [
            AdminRequestResponse(
                id=r.id,
                status=r.status,
                team_id=r.team_id,
                team_label=names[r.id].team_label,
                requester_id=r.requester_id,
                requester_name=names[r.id].requester_name,
                mentor_id=r.mentor_id,
                mentor_display_name=names[r.id].mentor_display_name,
                mentor_name=names[r.id].mentor_name,
                topic=r.topic,
                detail=r.detail,
                desired_times=r.desired_times,
                duration=r.duration,
                reject_reason=r.reject_reason,
                rejected_at=r.rejected_at,
                cancel_reason=r.cancel_reason,
                canceled_at=r.canceled_at,
                replaced_request_id=r.replaced_request_id,
                created_at=r.created_at,
            )
            for r in items
        ]

    async def public(self, items: list[MentoringRequest]) -> list[RequestResponse]:
        """수강생·멘토용 (멘토 실명 제외)."""
        return [
            RequestResponse(**r.model_dump(exclude={"mentor_name"}))
            for r in await self.admin(items)
        ]


PresenterDep = Annotated[Presenter, Depends(Presenter)]


# ---------------------------------------------------------------- 수강생
@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: RequestCreate, user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> RequestResponse:
    created = await service.create(
        user.id,
        RequestInput(
            topic=body.topic,
            detail=body.detail,
            desired_times=list(body.desired_times),
            duration=body.duration,
            cohort_id=body.cohort_id,
            mentor_id=body.mentor_id,
            team_id=body.team_id,
        ),
    )
    return (await presenter.public([created]))[0]


@router.post("/{request_id}/cancel", response_model=RequestResponse)
async def cancel_request(
    request_id: uuid.UUID,
    body: CancelBody,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> RequestResponse:
    """대기는 신청자만(보류 해제), 승인 후는 신청자·담당 멘토가 마감 전까지(전액 환불)."""
    canceled = await service.cancel(user.id, request_id, body.reason)
    return (await presenter.public([canceled]))[0]


@router.post(
    "/{request_id}/change", response_model=RequestResponse, status_code=status.HTTP_201_CREATED
)
async def change_request(
    request_id: uuid.UUID,
    body: ChangeBody,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> RequestResponse:
    """신청자만. 응답은 새 신청(replaced_request_id = 기존 신청)."""
    created = await service.change(
        user.id,
        request_id,
        ChangeInput(
            topic=body.topic,
            detail=body.detail,
            desired_times=list(body.desired_times),
            duration=body.duration,
        ),
    )
    return (await presenter.public([created]))[0]


@me_router.get("/mentoring/requests", response_model=Page[RequestResponse])
async def my_requests(
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
    status_: Annotated[MentoringRequestStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[RequestResponse]:
    items, total = await service.list_mine(user.id, status=status_, limit=limit, offset=offset)
    return Page(items=await presenter.public(items), total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------- 멘토
@me_router.get("/mentor-requests", response_model=Page[RequestResponse])
async def mentor_requests(
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
    status_: Annotated[MentoringRequestStatus | None, Query(alias="status")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[RequestResponse]:
    items, total = await service.list_for_mentor(
        user.id, status=status_, limit=limit, offset=offset
    )
    return Page(items=await presenter.public(items), total=total, limit=limit, offset=offset)


@router.post("/{request_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    request_id: uuid.UUID,
    body: ApproveBody,
    user: ApprovedUser,
    service: ApprovalDep,
    presenter: PresenterDep,
    sessions: Annotated[SessionPresenter, Depends(SessionPresenter)],
) -> ApprovalResponse:
    """그 신청의 멘토만. 보류 시간을 사용으로 옮기고 세션을 만든다."""
    approved, session = await service.approve(user.id, request_id, body.starts_at)
    return ApprovalResponse(
        request=(await presenter.public([approved]))[0],
        session=(await sessions.public([session]))[0],
    )


@router.post("/{request_id}/reject", response_model=RequestResponse)
async def reject_request(
    request_id: uuid.UUID,
    body: CancelBody,
    user: ApprovedUser,
    service: ApprovalDep,
    presenter: PresenterDep,
) -> RequestResponse:
    """그 신청의 멘토만, 사유 필수. 보류 시간을 돌려준다."""
    rejected = await service.reject(user.id, request_id, body.reason)
    return (await presenter.public([rejected]))[0]


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[AdminRequestResponse])
async def cohort_requests(
    cohort_id: uuid.UUID,
    _: RequestReader,
    service: ServiceDep,
    presenter: PresenterDep,
    status_: Annotated[MentoringRequestStatus | None, Query(alias="status")] = None,
    mentor_id: uuid.UUID | None = None,
    student_id: Annotated[
        uuid.UUID | None, Query(description="수강 등록(students.id)의 1:1 건만 (A59)")
    ] = None,
    team_id: Annotated[uuid.UUID | None, Query(description="이 팀의 건만 (A59)")] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminRequestResponse]:
    items, total = await service.list_by_cohort(
        cohort_id,
        status=status_,
        mentor_id=mentor_id,
        limit=limit,
        offset=offset,
        student_id=student_id,
        team_id=team_id,
    )
    return Page(items=await presenter.admin(items), total=total, limit=limit, offset=offset)


@admin_router.post("/{request_id}/cancel", response_model=AdminRequestResponse)
async def staff_cancel_request(
    cohort_id: uuid.UUID,
    request_id: uuid.UUID,
    body: StaffCancelBody,
    actor: RequestCanceler,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AdminRequestResponse:
    canceled = await service.staff_cancel(
        cohort_id, request_id, body.reason, refund=body.refund, actor_id=actor.id
    )
    return (await presenter.admin([canceled]))[0]

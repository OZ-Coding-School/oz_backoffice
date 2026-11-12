"""멘토링 신청 API (decisions A42, P11-1: 신청·승인 전 취소·조회).

수강생(승인된 회원):
  POST /mentoring/requests                    1:1(cohort_id·mentor_id) 또는 팀(team_id) 신청
  POST /mentoring/requests/{id}/cancel        승인 전 취소 (신청자만, 사유 필수)
  GET  /me/mentoring/requests?status=         본인 1:1 + 소속 팀 신청
멘토:
  GET  /me/mentor-requests?status=            받은 신청
운영진 (mentoring.request.read, 기수 범위):
  GET  /admin/cohorts/{cohort_id}/mentoring/requests?status=&mentor_id=
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
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.request_service import (
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
    TortoiseMentoringTeamRepository,
)
from app.contexts.mentoring.presentation.availability_router import get_available_times_service
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
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def get_request_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentoringRequestService:
    state = request.app.state
    return MentoringRequestService(
        requests=TortoiseMentoringRequestRepository(),
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
    )


ServiceDep = Annotated[MentoringRequestService, Depends(get_request_service)]


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


class Presenter:
    """신청자 이름·팀 이름·멘토 이름을 붙인다 (각각 한 번씩 묶어 조회)."""

    def __init__(self, request: Request) -> None:
        state = request.app.state
        self._students = cast("StudentLookup", state.student_queries)
        self._mentors = cast("MentorDirectory", state.mentor_queries)
        self._users = cast("UserQueries", state.user_queries)
        self._teams = TortoiseMentoringTeamRepository()

    async def admin(self, items: list[MentoringRequest]) -> list[AdminRequestResponse]:
        students = await self._students.get_many(list({r.requester_id for r in items}))
        teams = {
            t.id: t
            for t in await self._teams.list_by_ids(list({r.team_id for r in items if r.team_id}))
        }
        mentors = await self._mentors.get_many(list({r.mentor_id for r in items}))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        result = []
        for r in items:
            mentor = mentors.get(r.mentor_id)
            user = users.get(mentor.user_id) if mentor else None
            real = user.name if user else ""
            student = students.get(r.requester_id)
            team = teams.get(r.team_id) if r.team_id else None
            result.append(
                AdminRequestResponse(
                    id=r.id,
                    status=r.status,
                    team_id=r.team_id,
                    team_label=team.label if team else None,
                    requester_id=r.requester_id,
                    requester_name=student.name if student else "",
                    mentor_id=r.mentor_id,
                    mentor_display_name=mentor.display_name(real) if mentor else "",
                    mentor_name=real,
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
            )
        return result

    async def public(self, items: list[MentoringRequest]) -> list[RequestResponse]:
        """수강생·멘토용 (멘토 실명 제외)."""
        return [
            RequestResponse(**r.model_dump(exclude={"mentor_name"}))
            for r in await self.admin(items)
        ]


PresenterDep = Annotated[Presenter, Depends(Presenter)]
StatusFilter = Annotated[MentoringRequestStatus | None, Query()]


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
    """승인 전 취소 (신청자만). 보류 시간을 돌려준다."""
    canceled = await service.cancel(user.id, request_id, body.reason)
    return (await presenter.public([canceled]))[0]


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


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[AdminRequestResponse])
async def cohort_requests(
    cohort_id: uuid.UUID,
    _: RequestReader,
    service: ServiceDep,
    presenter: PresenterDep,
    status_: Annotated[MentoringRequestStatus | None, Query(alias="status")] = None,
    mentor_id: uuid.UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AdminRequestResponse]:
    items, total = await service.list_by_cohort(
        cohort_id, status=status_, mentor_id=mentor_id, limit=limit, offset=offset
    )
    return Page(items=await presenter.admin(items), total=total, limit=limit, offset=offset)

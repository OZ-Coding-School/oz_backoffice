"""기수 멘토 배정·멘토 활성화 API (decisions A35·A36).

mentoring.assignment.manage (기수 범위):
  GET/POST       /admin/cohorts/{cohort_id}/mentor-assignments          (목록은 페이징 없음)
  PATCH/DELETE   /admin/cohorts/{cohort_id}/mentor-assignments/{id}     (DELETE = 비활성화)
  POST           /admin/cohorts/{cohort_id}/mentor-assignments/{id}/reactivate
mentor.manage (범위가 하나라도 있으면):
  POST /admin/mentors/{mentor_id}/deactivate   (confirm=false 미리보기, true 실행)
  POST /admin/mentors/{mentor_id}/activate     (응답에 복구 후보 배정)
  POST /admin/mentors/{mentor_id}/mentor-assignments/reactivate   (가능한 것만)
멘토 본인:
  GET /me/mentor-assignments?include_inactive=   (정산 조건 포함)
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import (
    CohortLookup,
    CohortMentorService,
    MentorDirectory,
)
from app.contexts.mentoring.application.mentor_activation import MentorActivationService
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.contexts.mentoring.presentation.cleanup import build_cleanup
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork

admin_router = APIRouter(prefix="/admin", tags=["admin-mentor-assignments"])
me_router = APIRouter(prefix="/me/mentor-assignments", tags=["mentor-assignments"])

CohortManager = Annotated[
    User, Depends(require_permission("mentoring.assignment.manage", cohort_param="cohort_id"))
]
MentorManager = Annotated[User, Depends(require_permission("mentor.manage", any_scope=True))]
AssignmentPayUnit = Literal[PayUnit.HOURLY, PayUnit.PER_SESSION]


class CohortLabels:
    """academy `AcademyCatalog.cohort_labels` (본인 배정 목록의 과정명·기수 번호)."""

    def __init__(self, request: Request) -> None:
        self._catalog = request.app.state.academy_catalog

    async def of(self, cohort_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str, int]]:
        labels = await self._catalog.cohort_labels(cohort_ids)
        return {k: (v.bootcamp_name, v.cohort_number) for k, v in labels.items()}


def _mentors(request: Request) -> MentorDirectory:
    return cast("MentorDirectory", request.app.state.mentor_queries)


def get_assignment_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> CohortMentorService:
    return CohortMentorService(
        assignments=TortoiseCohortMentorRepository(),
        mentors=_mentors(request),
        cohorts=cast("CohortLookup", request.app.state.academy_catalog),
        cleanup=build_cleanup(request, clock),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


def get_activation_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentorActivationService:
    return MentorActivationService(
        mentors=_mentors(request),
        assignments=TortoiseCohortMentorRepository(),
        cleanup=build_cleanup(request, clock),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


class Presenter:
    """배정에 멘토 이름·표시 이름을 붙인다 (멘토·회원을 한 번씩 묶어 조회)."""

    def __init__(self, request: Request) -> None:
        self._mentors = _mentors(request)
        self._users = cast("UserQueries", request.app.state.user_queries)

    async def many(self, assignments: list[CohortMentor]) -> list["AssignmentResponse"]:
        mentors = await self._mentors.get_many(list({a.mentor_id for a in assignments}))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        items = []
        for a in assignments:
            mentor = mentors.get(a.mentor_id)
            user = users.get(mentor.user_id) if mentor else None
            name = user.name if user else ""
            items.append(
                AssignmentResponse.of(a, name, mentor.display_name(name) if mentor else name)
            )
        return items

    async def one(self, assignment: CohortMentor) -> "AssignmentResponse":
        return (await self.many([assignment]))[0]


ServiceDep = Annotated[CohortMentorService, Depends(get_assignment_service)]
ActivationDep = Annotated[MentorActivationService, Depends(get_activation_service)]
PresenterDep = Annotated[Presenter, Depends(Presenter)]
LabelsDep = Annotated[CohortLabels, Depends(CohortLabels)]


# ---------------------------------------------------------------- 스키마
class PayTerms(BaseModel):
    cost_settlement_policy: MentoringSettlementPolicy
    pay_unit: AssignmentPayUnit = Field(description="HOURLY / PER_SESSION")
    pay_rate: int = Field(ge=0, description="단가 (원)")
    no_show_pay_amount: int = Field(default=0, ge=0, description="노쇼 1건당 정산 금액 (원)")


class AssignmentCreate(PayTerms):
    mentor_id: uuid.UUID
    start_date: date = Field(description="기수 기간 안")
    end_date: date | None = Field(default=None, description="없으면 기한 없음, 기수 밖도 가능")


class AssignmentUpdate(BaseModel):
    """보낸 필드만 바꾼다. 종료일은 null로 비운다(기한 없음)."""

    start_date: date | None = None
    end_date: date | None = None
    cost_settlement_policy: MentoringSettlementPolicy | None = None
    pay_unit: AssignmentPayUnit | None = None
    pay_rate: int | None = Field(default=None, ge=0)
    no_show_pay_amount: int | None = Field(default=None, ge=0)


class AssignmentFields(PayTerms):
    id: uuid.UUID
    cohort_id: uuid.UUID
    start_date: date
    end_date: date | None
    is_active: bool
    deactivated_at: datetime | None
    deactivation_reason: CohortMentorDeactivationReason | None


class AssignmentResponse(AssignmentFields):
    mentor_id: uuid.UUID
    mentor_name: str = Field(description="실명")
    mentor_display_name: str = Field(description="수강생에게 보이는 이름")
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def of(cls, a: CohortMentor, name: str, display: str) -> "AssignmentResponse":
        return cls(
            **_fields(a),
            mentor_id=a.mentor_id,
            mentor_name=name,
            mentor_display_name=display,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )


class MyAssignmentResponse(AssignmentFields):
    bootcamp_name: str
    cohort_number: int


def _fields(a: CohortMentor) -> dict[str, object]:
    return {
        "id": a.id,
        "cohort_id": a.cohort_id,
        "start_date": a.start_date,
        "end_date": a.end_date,
        "cost_settlement_policy": a.cost_settlement_policy,
        "pay_unit": a.pay_unit,
        "pay_rate": a.pay_rate,
        "no_show_pay_amount": a.no_show_pay_amount,
        "is_active": a.is_active,
        "deactivated_at": a.deactivated_at,
        "deactivation_reason": a.deactivation_reason,
    }


class MentorDeactivateRequest(BaseModel):
    confirm: bool = Field(
        default=False, description="false면 미리보기만, true면 멘토와 활성 배정을 모두 비활성화"
    )


class MentorDeactivationResponse(BaseModel):
    mentor_id: uuid.UUID
    is_active: bool
    applied: bool = Field(description="실제로 비활성화했는지 (confirm=false면 false)")
    notice: str = Field(description="안내 문구")
    assignments: list[AssignmentResponse] = Field(description="함께 비활성화되는 활성 배정")
    pending_requests: int = Field(
        description="자동 취소된(미리보기면 취소될) 대기 신청 수. 승인된 세션은 유지 (A45)"
    )


class AssignmentDeactivateResponse(AssignmentResponse):
    canceled_pending_requests: int = Field(
        default=0, description="자동 취소된 대기 신청 수 (A42·A45)"
    )


class MentorActivationResponse(BaseModel):
    mentor_id: uuid.UUID
    is_active: bool
    restorable: list[AssignmentResponse] = Field(
        description="멘토 비활성화로 꺼진 배정 중 다시 켤 수 있는 후보 (추가 팝업)"
    )


class BulkReactivateRequest(BaseModel):
    assignment_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class ReactivationFailureResponse(BaseModel):
    assignment_id: uuid.UUID
    code: str
    message: str


class BulkReactivateResponse(BaseModel):
    reactivated: list[AssignmentResponse]
    failed: list[ReactivationFailureResponse]


# ---------------------------------------------------------------- 기수 배정
@admin_router.get(
    "/cohorts/{cohort_id}/mentor-assignments", response_model=list[AssignmentResponse]
)
async def list_assignments(
    cohort_id: uuid.UUID,
    _: CohortManager,
    service: ServiceDep,
    presenter: PresenterDep,
    include_inactive: bool = False,
) -> list[AssignmentResponse]:
    """한 기수의 배정 전체 (페이징 없음, A36). 기본은 활성 배정만."""
    assignments = await service.list_by_cohort(cohort_id, include_inactive=include_inactive)
    return await presenter.many(assignments)


@admin_router.post(
    "/cohorts/{cohort_id}/mentor-assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    cohort_id: uuid.UUID,
    body: AssignmentCreate,
    user: CohortManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AssignmentResponse:
    created = await service.create(cohort_id, body.model_dump(), actor_id=user.id)
    return await presenter.one(created)


@admin_router.patch(
    "/cohorts/{cohort_id}/mentor-assignments/{assignment_id}", response_model=AssignmentResponse
)
async def update_assignment(
    cohort_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: AssignmentUpdate,
    user: CohortManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AssignmentResponse:
    changes = body.model_dump(exclude_unset=True)
    changes = {k: v for k, v in changes.items() if v is not None or k == "end_date"}
    updated = await service.update(cohort_id, assignment_id, changes, actor_id=user.id)
    return await presenter.one(updated)


@admin_router.delete(
    "/cohorts/{cohort_id}/mentor-assignments/{assignment_id}",
    response_model=AssignmentDeactivateResponse,
)
async def deactivate_assignment(
    cohort_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: CohortManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AssignmentDeactivateResponse:
    """삭제 = 비활성화 (기록 보존, A35). 그 기수의 이 멘토 대기 신청은 자동 취소 (A42)."""
    assignment, canceled = await service.deactivate(cohort_id, assignment_id, actor_id=user.id)
    shown = await presenter.one(assignment)
    return AssignmentDeactivateResponse(**shown.model_dump(), canceled_pending_requests=canceled)


@admin_router.post(
    "/cohorts/{cohort_id}/mentor-assignments/{assignment_id}/reactivate",
    response_model=AssignmentResponse,
)
async def reactivate_assignment(
    cohort_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: CohortManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AssignmentResponse:
    return await presenter.one(await service.reactivate(cohort_id, assignment_id, actor_id=user.id))


# ---------------------------------------------------------------- 멘토 활성화
@admin_router.post("/mentors/{mentor_id}/deactivate", response_model=MentorDeactivationResponse)
async def deactivate_mentor(
    mentor_id: uuid.UUID,
    body: MentorDeactivateRequest,
    user: MentorManager,
    service: ActivationDep,
    presenter: PresenterDep,
) -> MentorDeactivationResponse:
    result = await service.deactivate(mentor_id, confirm=body.confirm, actor_id=user.id)
    count = len(result.assignments)
    notice = (
        f"멘토를 비활성화하면서 기수 배정 {count}건도 함께 비활성화하고 "
        f"대기 신청 {result.pending_requests}건을 취소했습니다."
        if result.applied
        else f"멘토를 비활성화하면 활성 기수 배정 {count}건도 함께 비활성화되고 "
        f"대기 신청 {result.pending_requests}건이 취소됩니다(승인된 세션은 유지). "
        "비활성화된 멘토는 새로 기수에 배정할 수 없습니다."
    )
    return MentorDeactivationResponse(
        mentor_id=mentor_id,
        is_active=result.mentor.is_active,
        applied=result.applied,
        notice=notice,
        assignments=await presenter.many(result.assignments),
        pending_requests=result.pending_requests,
    )


@admin_router.post("/mentors/{mentor_id}/activate", response_model=MentorActivationResponse)
async def activate_mentor(
    mentor_id: uuid.UUID, user: MentorManager, service: ActivationDep, presenter: PresenterDep
) -> MentorActivationResponse:
    result = await service.activate(mentor_id, actor_id=user.id)
    return MentorActivationResponse(
        mentor_id=mentor_id,
        is_active=result.mentor.is_active,
        restorable=await presenter.many(result.restorable),
    )


@admin_router.post(
    "/mentors/{mentor_id}/mentor-assignments/reactivate", response_model=BulkReactivateResponse
)
async def reactivate_mentor_assignments(
    mentor_id: uuid.UUID,
    body: BulkReactivateRequest,
    user: MentorManager,
    service: ActivationDep,
    presenter: PresenterDep,
) -> BulkReactivateResponse:
    """고른 배정 중 가능한 것만 켜고 나머지는 사유와 함께 돌려준다 (A36)."""
    result = await service.reactivate_assignments(mentor_id, body.assignment_ids, actor_id=user.id)
    return BulkReactivateResponse(
        reactivated=await presenter.many(result.reactivated),
        failed=[
            ReactivationFailureResponse(
                assignment_id=f.assignment_id, code=f.code, message=f.message
            )
            for f in result.failed
        ],
    )


# ---------------------------------------------------------------- 멘토 본인
@me_router.get("", response_model=list[MyAssignmentResponse])
async def list_my_assignments(
    user: ApprovedUser, service: ServiceDep, labels: LabelsDep, include_inactive: bool = False
) -> list[MyAssignmentResponse]:
    """본인 배정 (정산 조건 포함, A35). 기본은 활성 배정만."""
    assignments = await service.list_mine(user.id, include_inactive=include_inactive)
    found = await labels.of([a.cohort_id for a in assignments])
    return [
        MyAssignmentResponse(
            **_fields(a),
            bootcamp_name=found.get(a.cohort_id, ("", 0))[0],
            cohort_number=found.get(a.cohort_id, ("", 0))[1],
        )
        for a in assignments
    ]

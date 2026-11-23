"""멘토 일정 API: 불가 시간·신청 받기 (decisions A37).

멘토 본인(승인된 회원 + 멘토 프로필):   /me/mentor-schedule[...]
운영진 대리(mentor.manage):            /admin/mentors/{mentor_id}/schedule[...]

  GET             ...                            신청 받기 + 불가 시간(기본은 끝나지 않은 것)
  PUT             .../accepting                  신청 받기 켜기·끄기
  POST            .../unavailable-periods        불가 시간 등록 (?confirm=)
  PUT / DELETE    .../unavailable-periods/{id}   전체 교체(?confirm=)·삭제
불가 시간이 늘어나는 변경이 대기 신청·승인 세션과 충돌하면 `applied=false`와 충돌 목록을 돌려주고,
`confirm=true`로 다시 보내야 저장한다(충돌 검사는 P11부터 동작).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.schedule_conflicts import SessionScheduleConflicts
from app.contexts.mentoring.application.schedule_service import (
    MentorLookup,
    MentorSchedule,
    MentorScheduleService,
    ScheduleChange,
)
from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.contexts.mentoring.domain.schedule import (
    CATEGORY_MAX_LENGTH,
    REASON_MAX_LENGTH,
    MentorUnavailablePeriod,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentorUnavailablePeriodRepository,
)
from app.contexts.mentoring.presentation.cleanup import build_cleanup
from app.contexts.mentoring.presentation.presenters import NameBook
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork

me_router = APIRouter(prefix="/me/mentor-schedule", tags=["mentor-schedule"])
admin_router = APIRouter(
    prefix="/admin/mentors/{mentor_id}/schedule", tags=["admin-mentor-schedule"]
)

MentorManager = Annotated[User, Depends(require_permission("mentor.manage", any_scope=True))]
Confirm = Annotated[
    bool,
    Query(description="충돌하는 신청·세션이 있어도 저장한다 (대기 신청 반려, 세션 취소·전액 환불)"),
]
IncludePast = Annotated[bool, Query(description="끝난 불가 시간도 포함")]


def get_schedule_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentorScheduleService:
    cleanup = build_cleanup(request, clock)
    return MentorScheduleService(
        unavailable_periods=TortoiseMentorUnavailablePeriodRepository(),
        mentors=cast("MentorLookup", request.app.state.mentor_queries),
        conflicts=SessionScheduleConflicts(
            requests=TortoiseMentoringRequestRepository(),
            sessions=TortoiseMentoringSessionRepository(),
            cleanup=cleanup,
            clock=clock,
        ),
        cleanup=cleanup,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


ServiceDep = Annotated[MentorScheduleService, Depends(get_schedule_service)]


# ---------------------------------------------------------------- 스키마
class UnavailableInput(BaseModel):
    """불가 시간 (등록·전체 교체).

    - 일회성(ONCE): 시각(`starts_at~ends_at`) 또는 종일(`all_day=true`, `start_date~end_date`)
    - 매일(DAILY)·매주(WEEKLY): 기준 회차 `starts_at~ends_at`(24시간 이하, 자정 넘김 가능),
      매주는 `weekdays`(1=월~7=일), 반복 종료일 `repeat_until`(선택)
    시각은 한국 시각 정각·30분.
    """

    repeat: UnavailableRepeat = UnavailableRepeat.ONCE
    all_day: bool = False
    start_date: date | None = None
    end_date: date | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    weekdays: list[int] = Field(default_factory=list)
    repeat_until: date | None = None
    category: str | None = Field(default=None, max_length=CATEGORY_MAX_LENGTH)
    reason: str | None = Field(default=None, max_length=REASON_MAX_LENGTH)

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        if self.all_day:
            if self.repeat is not UnavailableRepeat.ONCE:
                raise ValueError("종일 입력은 일회성만 됩니다. 반복은 시각으로 입력합니다.")
            if self.start_date is None or self.end_date is None:
                raise ValueError("종일 일정은 start_date와 end_date가 필요합니다.")
        elif self.starts_at is None or self.ends_at is None:
            raise ValueError("starts_at과 ends_at이 필요합니다.")
        return self

    def to_entity(self, mentor_id: uuid.UUID) -> MentorUnavailablePeriod:
        if self.all_day:
            return MentorUnavailablePeriod.for_dates(
                mentor_id=mentor_id,
                start_date=cast("date", self.start_date),
                end_date=cast("date", self.end_date),
                category=self.category,
                reason=self.reason,
            )
        return MentorUnavailablePeriod(
            mentor_id=mentor_id,
            repeat=self.repeat,
            starts_at=cast("datetime", self.starts_at),
            ends_at=cast("datetime", self.ends_at),
            weekdays=frozenset(self.weekdays),
            repeat_until=self.repeat_until,
            category=self.category,
            reason=self.reason,
        )


class UnavailableResponse(BaseModel):
    id: uuid.UUID
    mentor_id: uuid.UUID
    repeat: UnavailableRepeat
    starts_at: datetime = Field(description="시작 (반복은 기준 회차)")
    ends_at: datetime
    all_day: bool = Field(description="한국 시각 00:00 ~ 00:00")
    weekdays: list[int]
    repeat_until: date | None
    category: str | None
    reason: str | None

    @classmethod
    def of(cls, p: MentorUnavailablePeriod) -> "UnavailableResponse":
        return cls(
            id=p.id,
            mentor_id=p.mentor_id,
            repeat=p.repeat,
            starts_at=p.starts_at,
            ends_at=p.ends_at,
            all_day=p.is_all_day,
            weekdays=sorted(p.weekdays),
            repeat_until=p.repeat_until,
            category=p.category,
            reason=p.reason,
        )


class ScheduleResponse(BaseModel):
    mentor_id: uuid.UUID
    accepting_requests: bool = Field(description="신청 받기. 꺼져 있으면 신청 가능 시간이 없다")
    unavailable_periods: list[UnavailableResponse]

    @classmethod
    def of(cls, schedule: MentorSchedule) -> "ScheduleResponse":
        return cls(
            mentor_id=schedule.mentor.id,
            accepting_requests=schedule.mentor.accepting_requests,
            unavailable_periods=[UnavailableResponse.of(p) for p in schedule.unavailable],
        )


class AcceptingRequest(BaseModel):
    accepting_requests: bool


class AcceptingResponse(BaseModel):
    mentor_id: uuid.UUID
    accepting_requests: bool
    canceled_pending_requests: int = Field(
        default=0, description="자동 취소된 대기 신청 수 (A42·A45)"
    )


class ConflictResponse(BaseModel):
    kind: Literal["REQUEST", "SESSION"] = Field(description="대기 신청 / 승인된 세션")
    target_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    topic: str = Field(description="신청·세션 주제 (A79)")
    requester_label: str = Field(description="팀이면 팀 이름, 1:1이면 수강생 이름 (A79)")


class ChangeResponse(BaseModel):
    applied: bool = Field(description="false면 충돌 미리보기 (confirm=true로 다시 요청)")
    unavailable_period: UnavailableResponse = Field(description="저장된(미리보기면 저장될) 값")
    conflicts: list[ConflictResponse] = Field(description="불가 시간에 걸리는 신청·세션")

    @classmethod
    def of(cls, change: ScheduleChange, details: dict[uuid.UUID, tuple[str, str]]) -> Self:
        return cls(
            applied=change.applied,
            unavailable_period=UnavailableResponse.of(change.period),
            conflicts=[
                ConflictResponse(
                    kind=c.kind,
                    target_id=c.target_id,
                    starts_at=c.starts_at,
                    ends_at=c.ends_at,
                    topic=details.get(c.target_id, ("", ""))[0],
                    requester_label=details.get(c.target_id, ("", ""))[1],
                )
                for c in change.conflicts
            ],
        )


class ConflictDetails:
    """충돌 대상 id → (주제, 신청자). 신청·세션을 묶어서 한 번씩 읽는다 (A79)."""

    def __init__(self, request: Request) -> None:
        self._names = NameBook(request)
        self._requests = TortoiseMentoringRequestRepository()
        self._sessions = TortoiseMentoringSessionRepository()

    async def of(self, change: ScheduleChange) -> dict[uuid.UUID, tuple[str, str]]:
        if not change.conflicts:
            return {}
        sessions = await self._sessions.get_many(
            [c.target_id for c in change.conflicts if c.kind == "SESSION"]
        )
        request_ids = [c.target_id for c in change.conflicts if c.kind == "REQUEST"]
        requests = await self._requests.get_many(
            request_ids + [s.request_id for s in sessions.values()]
        )
        names = await self._names.of(list(requests.values()))
        result: dict[uuid.UUID, tuple[str, str]] = {}
        for c in change.conflicts:
            session = sessions.get(c.target_id) if c.kind == "SESSION" else None
            req = requests.get(session.request_id if session else c.target_id)
            if req is None:
                continue
            n = names[req.id]
            label = n.team_label if req.team_id and n.team_label else n.requester_name
            result[c.target_id] = (session.topic if session else req.topic, label)
        return result


DetailsDep = Annotated[ConflictDetails, Depends(ConflictDetails)]


# ---------------------------------------------------------------- 공통 동작
async def _accepting(
    service: MentorScheduleService, mentor_id: uuid.UUID, body: AcceptingRequest, actor: uuid.UUID
) -> AcceptingResponse:
    mentor, canceled = await service.set_accepting(
        mentor_id, body.accepting_requests, actor_id=actor
    )
    return AcceptingResponse(
        mentor_id=mentor.id,
        accepting_requests=mentor.accepting_requests,
        canceled_pending_requests=canceled,
    )


async def _create(
    service: MentorScheduleService,
    mentor_id: uuid.UUID,
    body: UnavailableInput,
    confirm: bool,
    actor: uuid.UUID,
    response: Response,
    details: ConflictDetails,
) -> ChangeResponse:
    change = await service.create(body.to_entity(mentor_id), confirm=confirm, actor_id=actor)
    response.status_code = status.HTTP_201_CREATED if change.applied else status.HTTP_200_OK
    return ChangeResponse.of(change, await details.of(change))


async def _update(
    service: MentorScheduleService,
    mentor_id: uuid.UUID,
    period_id: uuid.UUID,
    body: UnavailableInput,
    confirm: bool,
    actor: uuid.UUID,
    details: ConflictDetails,
) -> ChangeResponse:
    change = await service.update(
        mentor_id, period_id, body.to_entity(mentor_id), confirm=confirm, actor_id=actor
    )
    return ChangeResponse.of(change, await details.of(change))


# ---------------------------------------------------------------- 멘토 본인
@me_router.get("", response_model=ScheduleResponse)
async def get_my_schedule(
    user: ApprovedUser, service: ServiceDep, include_past: IncludePast = False
) -> ScheduleResponse:
    mentor_id = await service.mentor_of_user(user.id)
    return ScheduleResponse.of(await service.view(mentor_id, include_past=include_past))


@me_router.put("/accepting", response_model=AcceptingResponse)
async def set_my_accepting(
    body: AcceptingRequest, user: ApprovedUser, service: ServiceDep
) -> AcceptingResponse:
    return await _accepting(service, await service.mentor_of_user(user.id), body, user.id)


@me_router.post("/unavailable-periods", response_model=ChangeResponse)
async def create_my_unavailable(
    body: UnavailableInput,
    user: ApprovedUser,
    service: ServiceDep,
    details: DetailsDep,
    response: Response,
    confirm: Confirm = False,
) -> ChangeResponse:
    """저장하면 201, 충돌 미리보기면 200 (applied=false)."""
    mentor_id = await service.mentor_of_user(user.id)
    return await _create(service, mentor_id, body, confirm, user.id, response, details)


@me_router.put("/unavailable-periods/{period_id}", response_model=ChangeResponse)
async def update_my_unavailable(
    period_id: uuid.UUID,
    body: UnavailableInput,
    user: ApprovedUser,
    service: ServiceDep,
    details: DetailsDep,
    confirm: Confirm = False,
) -> ChangeResponse:
    mentor_id = await service.mentor_of_user(user.id)
    return await _update(service, mentor_id, period_id, body, confirm, user.id, details)


@me_router.delete("/unavailable-periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_unavailable(
    period_id: uuid.UUID, user: ApprovedUser, service: ServiceDep
) -> Response:
    await service.delete(await service.mentor_of_user(user.id), period_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 운영진 대리
@admin_router.get("", response_model=ScheduleResponse)
async def get_mentor_schedule(
    mentor_id: uuid.UUID, _: MentorManager, service: ServiceDep, include_past: IncludePast = False
) -> ScheduleResponse:
    return ScheduleResponse.of(await service.view(mentor_id, include_past=include_past))


@admin_router.put("/accepting", response_model=AcceptingResponse)
async def set_mentor_accepting(
    mentor_id: uuid.UUID, body: AcceptingRequest, user: MentorManager, service: ServiceDep
) -> AcceptingResponse:
    return await _accepting(service, mentor_id, body, user.id)


@admin_router.post("/unavailable-periods", response_model=ChangeResponse)
async def create_mentor_unavailable(
    mentor_id: uuid.UUID,
    body: UnavailableInput,
    user: MentorManager,
    service: ServiceDep,
    details: DetailsDep,
    response: Response,
    confirm: Confirm = False,
) -> ChangeResponse:
    """저장하면 201, 충돌 미리보기면 200 (applied=false)."""
    return await _create(service, mentor_id, body, confirm, user.id, response, details)


@admin_router.put("/unavailable-periods/{period_id}", response_model=ChangeResponse)
async def update_mentor_unavailable(
    mentor_id: uuid.UUID,
    period_id: uuid.UUID,
    body: UnavailableInput,
    user: MentorManager,
    service: ServiceDep,
    details: DetailsDep,
    confirm: Confirm = False,
) -> ChangeResponse:
    return await _update(service, mentor_id, period_id, body, confirm, user.id, details)


@admin_router.delete("/unavailable-periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mentor_unavailable(
    mentor_id: uuid.UUID, period_id: uuid.UUID, user: MentorManager, service: ServiceDep
) -> Response:
    await service.delete(mentor_id, period_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

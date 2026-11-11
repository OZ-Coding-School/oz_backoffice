"""신청 가능 시간 조회 API (decisions A37).

GET /mentors/{mentor_id}/available-times?cohort_id=&from=&to=
- 그 기수의 수강 중 수강생, 운영진(mentoring.request.read 기수 범위), 멘토 본인.
- from·to는 한국 날짜(포함). 한 번에 최대 31일, 오늘부터 60일 뒤까지.
- 응답은 연속 가능 구간(UTC). 수강생은 구간 안에서 30분 경계 시작·진행 단위 배수 길이를 고른다.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.contexts.access.application.permissions import PermissionTarget
from app.contexts.access.presentation.dependencies import ApprovedUser, PermissionCheckerDep
from app.contexts.mentoring.application.availability_service import (
    AvailableTimesService,
    EnrollmentLookup,
    NoBusySchedule,
)
from app.contexts.mentoring.application.calendar import BusinessCalendar
from app.contexts.mentoring.application.schedule_service import MentorLookup
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseCohortMentorRepository,
    TortoiseMentoringBlockTimeRepository,
    TortoiseMentoringHolidayRepository,
    TortoiseMentorUnavailablePeriodRepository,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock

router = APIRouter(prefix="/mentors", tags=["mentor-available-times"])


def get_available_times_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> AvailableTimesService:
    return AvailableTimesService(
        settings=TortoiseCohortMentoringSettingsRepository(),
        assignments=TortoiseCohortMentorRepository(),
        unavailable_periods=TortoiseMentorUnavailablePeriodRepository(),
        blocks=TortoiseMentoringBlockTimeRepository(),
        calendar=BusinessCalendar(TortoiseMentoringHolidayRepository()),
        mentors=cast("MentorLookup", request.app.state.mentor_queries),
        enrollments=cast("EnrollmentLookup", request.app.state.student_queries),
        busy=NoBusySchedule(),
        clock=clock,
    )


ServiceDep = Annotated[AvailableTimesService, Depends(get_available_times_service)]


class IntervalResponse(BaseModel):
    starts_at: datetime
    ends_at: datetime


class AvailableTimesResponse(BaseModel):
    mentor_id: uuid.UUID
    cohort_id: uuid.UUID
    accepting_requests: bool = Field(description="false면 신청을 받지 않는다 (구간 없음)")
    allowed_duration: int = Field(description="진행 단위(분). 신청 시간은 이 값의 배수")
    min_lead_hours: int = Field(description="시작 N시간 전까지만 신청")
    intervals: list[IntervalResponse] = Field(description="연속 가능 구간 (시작 순)")


@router.get("/{mentor_id}/available-times", response_model=AvailableTimesResponse)
async def get_available_times(
    mentor_id: uuid.UUID,
    user: ApprovedUser,
    checker: PermissionCheckerDep,
    service: ServiceDep,
    cohort_id: uuid.UUID,
    start: Annotated[date, Query(alias="from", description="시작 날짜 (한국, 포함)")],
    end: Annotated[date, Query(alias="to", description="끝 날짜 (한국, 포함)")],
) -> AvailableTimesResponse:
    is_staff = await checker.has(
        user.id, "mentoring.request.read", PermissionTarget.cohort(cohort_id)
    )
    result = await service.query(
        mentor_id, cohort_id, start, end, viewer_id=user.id, viewer_is_staff=is_staff
    )
    return AvailableTimesResponse(
        mentor_id=result.mentor_id,
        cohort_id=result.cohort_id,
        accepting_requests=result.accepting_requests,
        allowed_duration=result.allowed_duration,
        min_lead_hours=result.min_lead_hours,
        intervals=[IntervalResponse(starts_at=i.start, ends_at=i.end) for i in result.intervals],
    )

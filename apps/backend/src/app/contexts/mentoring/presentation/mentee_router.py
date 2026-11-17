"""멘티 목록 API (운영진 멘티 관리, decisions A59).

mentoring.request.read (기수 범위):
  GET /admin/cohorts/{cohort_id}/mentoring/mentees?status=&q=&limit=&offset=

- status: 수강 상태(여러 번 줄 수 있음). 비우면 명단 전체(원천에서 삭제된 등록은 제외).
- q: 이름 부분 일치. 이름순.
- 건수는 1:1 기준이다: 대기 신청(PENDING), 예정 세션(SCHEDULED·IN_PROGRESS), 완료 세션(COMPLETED).
"""

import uuid
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.mentee_queries import (
    CohortRoster,
    MenteeQueries,
    MenteeSummary,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.pagination import Page
from app.shared.time import business_date

admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/mentees", tags=["admin-mentoring-mentees"]
)

MenteeReader = Annotated[
    User, Depends(require_permission("mentoring.request.read", cohort_param="cohort_id"))
]


def get_mentee_queries(request: Request) -> MenteeQueries:
    return MenteeQueries(
        roster=cast("CohortRoster", request.app.state.student_queries),
        teams=TortoiseMentoringTeamRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
    )


QueriesDep = Annotated[MenteeQueries, Depends(get_mentee_queries)]
ClockDep = Annotated[Clock, Depends(get_clock)]


class MenteeTeam(BaseModel):
    id: uuid.UUID
    label: str = Field(description="팀 이름, 없으면 'N팀'")


class MenteeAccount(BaseModel):
    id: uuid.UUID
    valid_from: date
    valid_until: date
    is_expired: bool
    total_minutes: int
    held_minutes: int
    used_minutes: int
    remaining_minutes: int


class MenteeResponse(BaseModel):
    student_id: uuid.UUID = Field(description="수강 등록(students.id)")
    name: str
    is_signed_up: bool = Field(description="회원 가입(계정 연결) 여부")
    status: EnrollmentStatus
    team: MenteeTeam | None
    account: MenteeAccount | None = Field(description="1:1 크레딧 (지급 전이면 없음)")
    pending_request_count: int = Field(description="1:1 대기 신청 수")
    upcoming_session_count: int = Field(description="1:1 예정·진행 중 세션 수")
    completed_session_count: int = Field(description="1:1 완료 세션 수")


def _response(m: MenteeSummary, today: date) -> MenteeResponse:
    a = m.account
    return MenteeResponse(
        student_id=m.student.id,
        name=m.student.name,
        is_signed_up=m.student.is_claimed,
        status=m.student.status,
        team=MenteeTeam(id=m.team.id, label=m.team.label) if m.team else None,
        account=MenteeAccount(
            id=a.id,
            valid_from=a.valid_from,
            valid_until=a.valid_until,
            is_expired=a.is_expired(today),
            total_minutes=a.total_minutes,
            held_minutes=a.held_minutes,
            used_minutes=a.used_minutes,
            remaining_minutes=a.remaining_minutes,
        )
        if a
        else None,
        pending_request_count=m.pending_requests,
        upcoming_session_count=m.upcoming_sessions,
        completed_session_count=m.completed_sessions,
    )


@admin_router.get("", response_model=Page[MenteeResponse])
async def list_mentees(
    cohort_id: uuid.UUID,
    _: MenteeReader,
    queries: QueriesDep,
    clock: ClockDep,
    status: Annotated[
        list[EnrollmentStatus] | None,
        Query(description="수강 상태 (여러 번 줄 수 있음, 비우면 전체)"),
    ] = None,
    q: Annotated[str | None, Query(max_length=50, description="이름 부분 일치")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MenteeResponse]:
    items, total = await queries.list(
        cohort_id, statuses=status or None, name=q, limit=limit, offset=offset
    )
    today = business_date(clock.now())
    return Page(items=[_response(m, today) for m in items], total=total, limit=limit, offset=offset)

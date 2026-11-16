"""멘토링 세션 조회 API (decisions A43, P11-2).

수강생:  GET /me/mentoring/sessions                본인 1:1 + 소속 팀 세션
멘토:    GET /me/mentor-sessions                    본인 세션
참여자:  GET /mentoring/sessions/{id}               1:1 신청 수강생·팀원·담당 멘토 (아니면 404)
운영진 (mentoring.request.read, 기수 범위):
         GET /admin/cohorts/{cohort_id}/mentoring/sessions?mentor_id=
         GET /admin/cohorts/{cohort_id}/mentoring/sessions/{id}
목록 필터: status, from(시작 시각 이상), to(시작 시각 미만). 시작 시각 최신순.
"""

import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.request_service import StudentLookup
from app.contexts.mentoring.application.session_service import MentoringSessionQueries
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.session import MentoringSession, SessionQuery
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.contexts.mentoring.presentation.presenters import NameBook
from app.core.pagination import Page

router = APIRouter(prefix="/mentoring/sessions", tags=["mentoring-sessions"])
me_router = APIRouter(prefix="/me", tags=["mentoring-sessions"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/sessions", tags=["admin-mentoring-sessions"]
)

SessionReader = Annotated[
    User, Depends(require_permission("mentoring.request.read", cohort_param="cohort_id"))
]


def get_session_queries(request: Request) -> MentoringSessionQueries:
    state = request.app.state
    return MentoringSessionQueries(
        sessions=TortoiseMentoringSessionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        teams=TortoiseMentoringTeamRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
    )


QueriesDep = Annotated[MentoringSessionQueries, Depends(get_session_queries)]


def session_query(
    status: Annotated[MentoringSessionStatus | None, Query()] = None,
    starts_from: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    starts_before: Annotated[AwareDatetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionQuery:
    return SessionQuery(
        status=status,
        starts_from=starts_from,
        starts_before=starts_before,
        limit=limit,
        offset=offset,
    )


QueryDep = Annotated[SessionQuery, Depends(session_query)]


class SessionResponse(BaseModel):
    id: uuid.UUID
    status: MentoringSessionStatus
    title: str
    topic: str
    detail: str = Field(description="신청 상세 내용")
    starts_at: datetime
    ends_at: datetime
    request_id: uuid.UUID
    team_id: uuid.UUID | None = Field(description="없으면 1:1")
    team_label: str | None
    requester_id: uuid.UUID = Field(description="신청한 수강 등록")
    requester_name: str
    mentor_id: uuid.UUID
    mentor_display_name: str
    google_meet_url: str | None = Field(
        description="Meet 링크. 공간을 만들기 전이거나 취소된 세션은 null (A48)"
    )
    summary: str | None = Field(description="기록 요약(완료) 또는 노쇼 사유. 수강생도 본다 (A53)")
    record_duration_minutes: int | None = Field(description="실제 진행 시간(분), 완료만")
    recorded_at: datetime | None = Field(description="기록 제출 시각")
    created_at: datetime | None


class AdminSessionResponse(SessionResponse):
    mentor_name: str = Field(description="멘토 실명 (운영진 응답에만)")
    actual_started_at: datetime | None = Field(description="Meet 실제 시작 (처음 회의)")
    actual_ended_at: datetime | None = Field(description="Meet 실제 종료 (마지막 회의)")


class SessionPresenter:
    def __init__(self, request: Request) -> None:
        self._names = NameBook(request)
        self._requests = TortoiseMentoringRequestRepository()

    async def admin(self, items: list[MentoringSession]) -> list[AdminSessionResponse]:
        requests = await self._requests.get_many(list({s.request_id for s in items}))
        names = await self._names.of(list(requests.values()))
        result = []
        for s in items:
            r = requests[s.request_id]
            n = names[r.id]
            result.append(
                AdminSessionResponse(
                    id=s.id,
                    status=s.status,
                    title=s.title,
                    topic=s.topic,
                    detail=r.detail,
                    starts_at=s.starts_at,
                    ends_at=s.ends_at,
                    request_id=r.id,
                    team_id=r.team_id,
                    team_label=n.team_label,
                    requester_id=r.requester_id,
                    requester_name=n.requester_name,
                    mentor_id=s.mentor_id,
                    mentor_display_name=n.mentor_display_name,
                    mentor_name=n.mentor_name,
                    google_meet_url=(
                        None if s.status is MentoringSessionStatus.CANCELED else s.google_meet_url
                    ),
                    summary=s.body,
                    record_duration_minutes=s.record_duration_minutes,
                    recorded_at=s.recorded_at,
                    actual_started_at=s.actual_started_at,
                    actual_ended_at=s.actual_ended_at,
                    created_at=s.created_at,
                )
            )
        return result

    async def public(self, items: list[MentoringSession]) -> list[SessionResponse]:
        """수강생·멘토용 (멘토 실명 제외)."""
        return [
            SessionResponse(
                **s.model_dump(exclude={"mentor_name", "actual_started_at", "actual_ended_at"})
            )
            for s in await self.admin(items)
        ]


PresenterDep = Annotated[SessionPresenter, Depends(SessionPresenter)]


@me_router.get("/mentoring/sessions", response_model=Page[SessionResponse])
async def my_sessions(
    user: ApprovedUser, queries: QueriesDep, presenter: PresenterDep, query: QueryDep
) -> Page[SessionResponse]:
    items, total = await queries.list_mine(user.id, query)
    return Page(
        items=await presenter.public(items), total=total, limit=query.limit, offset=query.offset
    )


@me_router.get("/mentor-sessions", response_model=Page[SessionResponse])
async def mentor_sessions(
    user: ApprovedUser, queries: QueriesDep, presenter: PresenterDep, query: QueryDep
) -> Page[SessionResponse]:
    items, total = await queries.list_for_mentor(user.id, query)
    return Page(
        items=await presenter.public(items), total=total, limit=query.limit, offset=query.offset
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID, user: ApprovedUser, queries: QueriesDep, presenter: PresenterDep
) -> SessionResponse:
    session = await queries.get_for_user(user.id, session_id)
    return (await presenter.public([session]))[0]


@admin_router.get("", response_model=Page[AdminSessionResponse])
async def cohort_sessions(
    cohort_id: uuid.UUID,
    _: SessionReader,
    queries: QueriesDep,
    presenter: PresenterDep,
    query: QueryDep,
    mentor_id: uuid.UUID | None = None,
    student_id: Annotated[
        uuid.UUID | None, Query(description="수강 등록(students.id)의 1:1 건만 (A59)")
    ] = None,
    team_id: Annotated[uuid.UUID | None, Query(description="이 팀의 건만 (A59)")] = None,
) -> Page[AdminSessionResponse]:
    items, total = await queries.list_by_cohort(
        cohort_id, mentor_id=mentor_id, query=query, student_id=student_id, team_id=team_id
    )
    return Page(
        items=await presenter.admin(items), total=total, limit=query.limit, offset=query.offset
    )


@admin_router.get("/{session_id}", response_model=AdminSessionResponse)
async def cohort_session(
    cohort_id: uuid.UUID,
    session_id: uuid.UUID,
    _: SessionReader,
    queries: QueriesDep,
    presenter: PresenterDep,
) -> AdminSessionResponse:
    session = await queries.get_for_cohort(cohort_id, session_id)
    return (await presenter.admin([session]))[0]

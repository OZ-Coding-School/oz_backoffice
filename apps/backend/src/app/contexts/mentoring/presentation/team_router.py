"""멘토링 팀 API (decisions M11·A39).

mentoring.team.manage (기수 범위):
  GET/POST       /admin/cohorts/{cohort_id}/mentoring-teams     (목록은 페이징 없음)
  GET            /admin/cohorts/{cohort_id}/mentoring-teams/unassigned-students
  PATCH/DELETE   /admin/cohorts/{cohort_id}/mentoring-teams/{team_id}       (이름·담당 멘토 / 삭제)
  POST           /admin/cohorts/{cohort_id}/mentoring-teams/{team_id}/members
  DELETE         /admin/cohorts/{cohort_id}/mentoring-teams/{team_id}/members/{student_id}
본인:
  GET /me/mentoring-teams   (수강생은 소속 팀, 멘토는 담당 팀)
"""

import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.team_service import (
    MentoringTeamService,
    MentorOfUser,
    StudentLookup,
)
from app.contexts.mentoring.domain.team import NAME_MAX_LENGTH, MentoringTeam, TeamActivity
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseCohortMentorRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.contexts.mentoring.presentation.cleanup import build_cleanup
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork

admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring-teams", tags=["admin-mentoring-teams"]
)
me_router = APIRouter(prefix="/me/mentoring-teams", tags=["mentoring-teams"])

TeamManager = Annotated[
    User, Depends(require_permission("mentoring.team.manage", cohort_param="cohort_id"))
]
TeamReader = Annotated[
    User, Depends(require_permission("mentoring.team.read", cohort_param="cohort_id"))
]


def get_team_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> MentoringTeamService:
    state = request.app.state
    return MentoringTeamService(
        cleanup=build_cleanup(request, clock),
        teams=TortoiseMentoringTeamRepository(),
        settings=TortoiseCohortMentoringSettingsRepository(),
        assignments=TortoiseCohortMentorRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorOfUser", state.mentor_queries),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
    )


ServiceDep = Annotated[MentoringTeamService, Depends(get_team_service)]


# ---------------------------------------------------------------- 스키마
class TeamCreate(BaseModel):
    mentor_id: uuid.UUID = Field(description="그 기수에 활성 배정된 멘토")
    name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class TeamUpdate(BaseModel):
    """보낸 필드만 바꾼다. 이름은 null로 비운다(팀 번호로 표시)."""

    name: str | None = Field(default=None, max_length=NAME_MAX_LENGTH)
    mentor_id: uuid.UUID | None = None


class MemberAdd(BaseModel):
    student_id: uuid.UUID


class StudentSummary(BaseModel):
    student_id: uuid.UUID
    name: str
    is_signed_up: bool = Field(description="회원 가입(계정 연결) 여부")
    status: EnrollmentStatus

    @classmethod
    def of(cls, s: Student) -> "StudentSummary":
        return cls(student_id=s.id, name=s.name, is_signed_up=s.is_claimed, status=s.status)


class MentorSummary(BaseModel):
    mentor_id: uuid.UUID
    name: str = Field(description="실명 (운영진·멘토 본인 응답에만)")
    display_name: str = Field(description="수강생에게 보이는 이름")


class TeamResponse(BaseModel):
    id: uuid.UUID
    cohort_id: uuid.UUID
    team_number: int
    name: str | None
    label: str = Field(description="팀 이름, 없으면 'N팀'")
    mentor: MentorSummary
    members: list[StudentSummary]


class StudentTeamMentor(BaseModel):
    mentor_id: uuid.UUID
    display_name: str
    headline: str | None = Field(default=None, description="한 줄 소개 (A73)")
    expertise: str | None = Field(default=None, description="전문 분야, 쉼표로 구분 (A73)")
    accepting_requests: bool = Field(default=False, description="신청 받는 중 (A73)")


class StudentTeamMember(BaseModel):
    student_id: uuid.UUID
    name: str
    status: EnrollmentStatus | None = Field(default=None, description="수강 상태 (A73)")


class TeamStats(BaseModel):
    """내 팀 집계 (A73). 진행 시간은 기록 기준."""

    completed_sessions: int
    completed_minutes: int
    upcoming_sessions: int = Field(description="예정·진행 중 세션 수")
    next_session_at: datetime | None = Field(description="가장 이른 예정·진행 중 세션 시작")
    pending_requests: int = Field(description="승인 대기 팀 신청 수")
    pending_requester_name: str | None = Field(description="가장 먼저 낸 대기 신청의 신청자")


class TeamChangeResponse(TeamResponse):
    canceled_pending_requests: int = Field(
        default=0, description="자동 취소된 대기 신청 수 (A42·A45)"
    )


class StudentTeamResponse(BaseModel):
    """수강생이 보는 내 팀 (멘토 실명·가입 여부 제외)."""

    id: uuid.UUID
    cohort_id: uuid.UUID
    team_number: int
    label: str
    created_at: datetime | None = Field(default=None, description="팀 구성일 (A73)")
    mentor: StudentTeamMentor
    members: list[StudentTeamMember]
    stats: TeamStats


class MyTeamsResponse(BaseModel):
    as_student: list[StudentTeamResponse]
    as_mentor: list[TeamResponse]


class Presenter:
    """팀에 멘토 이름·팀원 정보를 붙인다 (멘토·회원·수강생을 한 번씩 묶어 조회)."""

    def __init__(self, request: Request, service: ServiceDep) -> None:
        self._mentors = cast("MentorDirectory", request.app.state.mentor_queries)
        self._users = cast("UserQueries", request.app.state.user_queries)
        self._service = service

    async def _mentor_names(self, teams: list[MentoringTeam]) -> dict[uuid.UUID, MentorSummary]:
        mentors = await self._mentors.get_many(list({t.mentor_id for t in teams}))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        result = {}
        for mentor in mentors.values():
            user = users.get(mentor.user_id)
            name = user.name if user else ""
            result[mentor.id] = MentorSummary(
                mentor_id=mentor.id, name=name, display_name=mentor.display_name(name)
            )
        return result

    async def teams(self, teams: list[MentoringTeam]) -> list[TeamResponse]:
        mentors = await self._mentor_names(teams)
        students = await self._service.students_of(teams)
        return [
            TeamResponse(
                id=t.id,
                cohort_id=t.cohort_id,
                team_number=t.team_number,
                name=t.name,
                label=t.label,
                mentor=mentors.get(t.mentor_id)
                or MentorSummary(mentor_id=t.mentor_id, name="", display_name=""),
                members=[StudentSummary.of(students[m]) for m in t.member_ids if m in students],
            )
            for t in teams
        ]

    async def team(self, team: MentoringTeam) -> TeamResponse:
        return (await self.teams([team]))[0]

    async def student_view(self, teams: list[MentoringTeam]) -> list[StudentTeamResponse]:
        """수강생의 내 팀 (A73): 멘토 소개·팀원 수강 상태·팀 세션/신청 집계를 붙인다."""
        mentors = await self._mentors.get_many(list({t.mentor_id for t in teams}))
        names = await self._mentor_names(teams)
        students = await self._service.students_of(teams)
        ids = [t.id for t in teams]
        activity = await TortoiseMentoringSessionRepository().team_activity(ids)
        pending = await TortoiseMentoringRequestRepository().pending_by_teams(ids)
        result = []
        for t in teams:
            mentor = mentors.get(t.mentor_id)
            act = activity.get(t.id, TeamActivity())
            count, first = pending.get(t.id, (0, None))
            first_student = students.get(first) if first else None
            result.append(
                StudentTeamResponse(
                    id=t.id,
                    cohort_id=t.cohort_id,
                    team_number=t.team_number,
                    label=t.label,
                    created_at=t.created_at,
                    mentor=StudentTeamMentor(
                        mentor_id=t.mentor_id,
                        display_name=names[t.mentor_id].display_name
                        if t.mentor_id in names
                        else "",
                        headline=mentor.headline if mentor else None,
                        expertise=mentor.expertise if mentor else None,
                        accepting_requests=mentor.accepting_requests if mentor else False,
                    ),
                    members=[
                        StudentTeamMember(
                            student_id=m, name=students[m].name, status=students[m].status
                        )
                        for m in t.member_ids
                        if m in students
                    ],
                    stats=TeamStats(
                        completed_sessions=act.completed_sessions,
                        completed_minutes=act.completed_minutes,
                        upcoming_sessions=act.upcoming_sessions,
                        next_session_at=act.next_session_at,
                        pending_requests=count,
                        pending_requester_name=first_student.name if first_student else None,
                    ),
                )
            )
        return result


PresenterDep = Annotated[Presenter, Depends(Presenter)]


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=list[TeamResponse])
async def list_teams(
    cohort_id: uuid.UUID,
    _: TeamReader,
    service: ServiceDep,
    presenter: PresenterDep,
) -> list[TeamResponse]:
    """기수의 팀 전체 (페이징 없음, A39). 팀 번호 순."""
    return await presenter.teams(await service.list_by_cohort(cohort_id))


@admin_router.get("/unassigned-students", response_model=list[StudentSummary])
async def list_unassigned_students(
    cohort_id: uuid.UUID,
    _: TeamReader,
    service: ServiceDep,
) -> list[StudentSummary]:
    """팀이 없는 수강 중 수강생 (가입 여부 무관, 이름순)."""
    return [StudentSummary.of(s) for s in await service.unassigned_students(cohort_id)]


@admin_router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    cohort_id: uuid.UUID,
    body: TeamCreate,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamResponse:
    team = await service.create(
        cohort_id,
        mentor_id=body.mentor_id,
        name=body.name,
        student_ids=body.student_ids,
        actor_id=user.id,
    )
    return await presenter.team(team)


@admin_router.patch("/{team_id}", response_model=TeamChangeResponse)
async def update_team(
    cohort_id: uuid.UUID,
    team_id: uuid.UUID,
    body: TeamUpdate,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamChangeResponse:
    """담당 멘토를 바꾸면 그 팀의 대기 신청은 자동 취소 (A42)."""
    changes = body.model_dump(exclude_unset=True)
    if changes.get("mentor_id", "") is None:
        del changes["mentor_id"]  # 담당 멘토는 비울 수 없다
    team, canceled = await service.update(cohort_id, team_id, changes, actor_id=user.id)
    shown = await presenter.team(team)
    return TeamChangeResponse(**shown.model_dump(), canceled_pending_requests=canceled)


@admin_router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    cohort_id: uuid.UUID, team_id: uuid.UUID, user: TeamManager, service: ServiceDep
) -> Response:
    """시간 계좌·신청이 있는 팀은 409 `team_in_use`."""
    await service.delete(cohort_id, team_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/{team_id}/members", response_model=TeamResponse)
async def add_member(
    cohort_id: uuid.UUID,
    team_id: uuid.UUID,
    body: MemberAdd,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamResponse:
    team = await service.add_member(cohort_id, team_id, body.student_id, actor_id=user.id)
    return await presenter.team(team)


@admin_router.delete("/{team_id}/members/{student_id}", response_model=TeamChangeResponse)
async def remove_member(
    cohort_id: uuid.UUID,
    team_id: uuid.UUID,
    student_id: uuid.UUID,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamChangeResponse:
    """그 팀원이 신청한 팀 대기 신청은 자동 취소 (A45)."""
    team, canceled = await service.remove_member(cohort_id, team_id, student_id, actor_id=user.id)
    shown = await presenter.team(team)
    return TeamChangeResponse(**shown.model_dump(), canceled_pending_requests=canceled)


# ---------------------------------------------------------------- 본인
@me_router.get("", response_model=MyTeamsResponse)
async def my_teams(
    user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> MyTeamsResponse:
    mine = await service.mine(user.id)
    return MyTeamsResponse(
        as_student=await presenter.student_view(mine.as_student),
        as_mentor=await presenter.teams(mine.as_mentor),
    )

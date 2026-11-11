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
from app.contexts.mentoring.domain.team import NAME_MAX_LENGTH, MentoringTeam
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseCohortMentorRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.uow import UnitOfWork

admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring-teams", tags=["admin-mentoring-teams"]
)
me_router = APIRouter(prefix="/me/mentoring-teams", tags=["mentoring-teams"])

TeamManager = Annotated[
    User, Depends(require_permission("mentoring.team.manage", cohort_param="cohort_id"))
]


def get_team_service(request: Request) -> MentoringTeamService:
    state = request.app.state
    return MentoringTeamService(
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


class StudentTeamMember(BaseModel):
    student_id: uuid.UUID
    name: str


class StudentTeamResponse(BaseModel):
    """수강생이 보는 내 팀 (멘토 실명·팀원 상태 제외)."""

    id: uuid.UUID
    cohort_id: uuid.UUID
    team_number: int
    label: str
    mentor: StudentTeamMentor
    members: list[StudentTeamMember]


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
        full = await self.teams(teams)
        return [
            StudentTeamResponse(
                id=t.id,
                cohort_id=t.cohort_id,
                team_number=t.team_number,
                label=t.label,
                mentor=StudentTeamMentor(
                    mentor_id=t.mentor.mentor_id, display_name=t.mentor.display_name
                ),
                members=[
                    StudentTeamMember(student_id=m.student_id, name=m.name) for m in t.members
                ],
            )
            for t in full
        ]


PresenterDep = Annotated[Presenter, Depends(Presenter)]


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=list[TeamResponse])
async def list_teams(
    cohort_id: uuid.UUID,
    _: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> list[TeamResponse]:
    """기수의 팀 전체 (페이징 없음, A39). 팀 번호 순."""
    return await presenter.teams(await service.list_by_cohort(cohort_id))


@admin_router.get("/unassigned-students", response_model=list[StudentSummary])
async def list_unassigned_students(
    cohort_id: uuid.UUID,
    _: TeamManager,
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


@admin_router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    cohort_id: uuid.UUID,
    team_id: uuid.UUID,
    body: TeamUpdate,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamResponse:
    changes = body.model_dump(exclude_unset=True)
    if changes.get("mentor_id", "") is None:
        del changes["mentor_id"]  # 담당 멘토는 비울 수 없다
    team = await service.update(cohort_id, team_id, changes, actor_id=user.id)
    return await presenter.team(team)


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


@admin_router.delete("/{team_id}/members/{student_id}", response_model=TeamResponse)
async def remove_member(
    cohort_id: uuid.UUID,
    team_id: uuid.UUID,
    student_id: uuid.UUID,
    user: TeamManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> TeamResponse:
    team = await service.remove_member(cohort_id, team_id, student_id, actor_id=user.id)
    return await presenter.team(team)


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

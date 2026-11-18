"""수강생 멘토링 신청 준비 API (decisions A64, BE-1). 그 기수의 수강 중 수강생만.

GET /me/mentoring/settings?cohort_id=             기수 멘토링 설정 요약 (신청 화면용 네 값)
GET /me/mentoring/mentors?cohort_id=              신청 받는 멘토 목록 (표시 이름순)
GET /me/mentoring/mentors/{mentor_id}?cohort_id=  멘토 공개 프로필 (배정 멘토면 신청을 안 받아도)
공개 프로필에는 실명·연락처를 넣지 않는다(표시 이름만). 사진은 presigned GET(만료 10분, A28).
"""

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.mentoring.application.availability_service import EnrollmentLookup
from app.contexts.mentoring.application.student_queries import (
    MentorProfiles,
    StudentMentoringQueries,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseCohortMentorRepository,
)
from app.core.dependencies import get_file_storage
from app.integrations.s3 import S3Storage

router = APIRouter(prefix="/me/mentoring", tags=["student-mentoring"])


def get_student_mentoring_queries(request: Request) -> StudentMentoringQueries:
    state = request.app.state
    return StudentMentoringQueries(
        settings=TortoiseCohortMentoringSettingsRepository(),
        assignments=TortoiseCohortMentorRepository(),
        mentors=cast("MentorProfiles", state.mentor_queries),
        enrollments=cast("EnrollmentLookup", state.student_queries),
    )


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


QueriesDep = Annotated[StudentMentoringQueries, Depends(get_student_mentoring_queries)]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]
StorageDep = Annotated[S3Storage, Depends(get_file_storage)]


class MentoringSettingsSummary(BaseModel):
    cohort_id: uuid.UUID
    allow_1_on_1: bool = Field(description="1:1 멘토링 허용")
    allow_team_mentoring: bool = Field(description="팀 멘토링 허용 ('내 팀' 메뉴도 이때만)")
    allowed_duration: int = Field(description="진행 단위(분, 30 또는 60). 진행 시간은 이 값의 배수")
    min_lead_hours: int = Field(description="시작 N시간 전까지 신청")
    max_pending_requests: int = Field(description="승인 대기 신청 최대 건수")


class MentorCard(BaseModel):
    mentor_id: uuid.UUID
    display_name: str = Field(description="수강생에게 보이는 이름 (실명 또는 닉네임, 멘토가 고름)")
    headline: str | None
    expertise: str | None
    profile_image_url: str | None = Field(description="presigned GET (만료 10분)")


class MentorProfileResponse(MentorCard):
    introduction: str | None
    accepting_requests: bool = Field(description="false면 지금은 1:1 신청을 받지 않는다")


async def _display_names(mentors: list[Mentor], users: UserQueries) -> dict[uuid.UUID, str]:
    found = await users.get_many([m.user_id for m in mentors])
    return {
        m.id: m.display_name(user.name if (user := found.get(m.user_id)) else "") for m in mentors
    }


async def _image_url(mentor: Mentor, storage: S3Storage) -> str | None:
    if mentor.profile_image_key is None:
        return None
    return await storage.presign_get(mentor.profile_image_key)


@router.get("/settings", response_model=MentoringSettingsSummary)
async def mentoring_settings(
    cohort_id: uuid.UUID, user: ApprovedUser, queries: QueriesDep
) -> MentoringSettingsSummary:
    """설정이 없으면 404 `mentoring_settings_not_configured`."""
    s = await queries.settings(user.id, cohort_id)
    return MentoringSettingsSummary(
        cohort_id=cohort_id,
        allow_1_on_1=s.allow_1_on_1,
        allow_team_mentoring=s.allow_team_mentoring,
        allowed_duration=s.allowed_duration,
        min_lead_hours=s.min_lead_hours,
        max_pending_requests=s.max_pending_requests,
    )


@router.get("/mentors", response_model=list[MentorCard])
async def accepting_mentors(
    cohort_id: uuid.UUID,
    user: ApprovedUser,
    queries: QueriesDep,
    users: UsersDep,
    storage: StorageDep,
) -> list[MentorCard]:
    """신청 받는 멘토 (표시 이름순). 기수 멘토 수는 적어 페이지를 나누지 않는다."""
    mentors = await queries.accepting_mentors(user.id, cohort_id)
    names = await _display_names(mentors, users)
    cards = [
        MentorCard(
            mentor_id=m.id,
            display_name=names[m.id],
            headline=m.headline,
            expertise=m.expertise,
            profile_image_url=await _image_url(m, storage),
        )
        for m in mentors
    ]
    return sorted(cards, key=lambda c: (c.display_name, c.mentor_id))


@router.get("/mentors/{mentor_id}", response_model=MentorProfileResponse)
async def mentor_profile(
    mentor_id: uuid.UUID,
    cohort_id: uuid.UUID,
    user: ApprovedUser,
    queries: QueriesDep,
    users: UsersDep,
    storage: StorageDep,
) -> MentorProfileResponse:
    """그 기수에 배정되지 않았으면 404 `mentor_not_assigned`."""
    m = await queries.mentor(user.id, cohort_id, mentor_id)
    names = await _display_names([m], users)
    return MentorProfileResponse(
        mentor_id=m.id,
        display_name=names[m.id],
        headline=m.headline,
        expertise=m.expertise,
        introduction=m.introduction,
        profile_image_url=await _image_url(m, storage),
        accepting_requests=m.accepting_requests,
    )

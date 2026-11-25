"""멘토 프로필 API (decisions A22, A28).

- 멘토 본인(승인된 회원 + 멘토 프로필): GET/PATCH `/me/mentor-profile`,
  사진 업로드 요청·확정, 사진 삭제
- 운영진(mentor.manage, decisions A36): GET `/admin/mentors`(목록·검색),
  GET/PATCH `/admin/mentors/{id}/profile`,
  사진 대리 업로드·삭제
사진은 브라우저가 최적화해 올린다. 서버는 PNG·JPEG·WebP 2MB 이하인지와 형식만 검사한다.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_cohorts import MentorCohortReader
from app.contexts.educator.application.mentor_profiles import MentorProfileService
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import (
    EXPERTISE_MAX_LENGTH,
    HEADLINE_MAX_LENGTH,
    INTRODUCTION_MAX_LENGTH,
    NICKNAME_MAX_LENGTH,
    Mentor,
)
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseMentorRepository,
)
from app.contexts.educator.presentation.admin_router import UploadTicketResponse, get_direct_uploads
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.core.dependencies import get_file_storage
from app.core.pagination import Page
from app.core.uow import UnitOfWork
from app.integrations.s3 import S3Storage

me_router = APIRouter(prefix="/me/mentor-profile", tags=["mentor-profile"])
admin_router = APIRouter(prefix="/admin/mentors", tags=["admin-mentors"])

Manager = Annotated[User, Depends(require_permission("educator.mentor.manage", any_scope=True))]
Reader = Annotated[User, Depends(require_permission("educator.mentor.read", any_scope=True))]


def get_mentor_profile_service(
    request: Request,
    uploads: Annotated[DirectUploads, Depends(get_direct_uploads)],
    storage: Annotated[S3Storage, Depends(get_file_storage)],
) -> MentorProfileService:
    return MentorProfileService(
        mentors=TortoiseMentorRepository(),
        contracts=TortoiseEducatorContractRepository(),
        uploads=uploads,
        storage=storage,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


ProfilesDep = Annotated[MentorProfileService, Depends(get_mentor_profile_service)]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]
ImageType = Literal["image/png", "image/jpeg", "image/webp"]


# ---------------------------------------------------------------- 스키마
class ProfileUpdate(BaseModel):
    """보낸 필드만 바꾼다. 닉네임·한 줄 소개·소개·전문 분야는 null(또는 빈 값)로 비운다."""

    nickname: str | None = Field(default=None, max_length=NICKNAME_MAX_LENGTH)
    display_name_preference: DisplayNamePreference | None = None
    headline: str | None = Field(default=None, max_length=HEADLINE_MAX_LENGTH)
    introduction: str | None = Field(default=None, max_length=INTRODUCTION_MAX_LENGTH)
    expertise: str | None = Field(default=None, max_length=EXPERTISE_MAX_LENGTH)


class ImageUploadRequest(BaseModel):
    content_type: ImageType


class MentorProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str = Field(description="실명 (회원 이름)")
    display_name: str = Field(description="수강생에게 보이는 이름 (표시 이름 선택 반영)")
    nickname: str | None
    display_name_preference: DisplayNamePreference
    headline: str | None
    introduction: str | None
    expertise: str | None
    profile_image_url: str | None = Field(description="presigned GET (만료 10분)")
    is_active: bool


class MentorCohortItem(BaseModel):
    cohort_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int


class MentorListItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    phone_number: str | None
    display_name: str
    is_active: bool
    contract_count: int
    created_at: datetime | None
    accepting_requests: bool = Field(description="신청 받기 (A37)")
    active_cohorts: list[MentorCohortItem] = Field(
        default_factory=list, description="활성 배정 기수, 최근 배정부터 (A100)"
    )


def display_name(mentor: Mentor, real_name: str) -> str:
    return mentor.display_name(real_name)


async def _profile(
    mentor: Mentor, profiles: MentorProfileService, users: UserQueries
) -> MentorProfileResponse:
    user = await users.get(mentor.user_id)
    name = user.name if user else ""
    return MentorProfileResponse(
        id=mentor.id,
        user_id=mentor.user_id,
        name=name,
        display_name=display_name(mentor, name),
        nickname=mentor.nickname,
        display_name_preference=mentor.display_name_preference,
        headline=mentor.headline,
        introduction=mentor.introduction,
        expertise=mentor.expertise,
        profile_image_url=await profiles.image_url(mentor),
        is_active=mentor.is_active,
    )


def _changes(body: ProfileUpdate) -> dict[str, object]:
    changes = body.model_dump(exclude_unset=True)
    if changes.get("display_name_preference", "") is None:
        del changes["display_name_preference"]  # 표시 이름 선택은 비울 수 없다
    return changes


def _ticket(ticket: object) -> UploadTicketResponse:
    return UploadTicketResponse.model_validate(ticket, from_attributes=True)


# ---------------------------------------------------------------- 멘토 본인
@me_router.get("", response_model=MentorProfileResponse)
async def get_my_profile(
    user: ApprovedUser, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    return await _profile(await profiles.get_by_user(user.id), profiles, users)


@me_router.patch("", response_model=MentorProfileResponse)
async def update_my_profile(
    body: ProfileUpdate, user: ApprovedUser, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    mentor = await profiles.get_by_user(user.id)
    updated = await profiles.update(mentor.id, _changes(body), actor_id=user.id)
    return await _profile(updated, profiles, users)


@me_router.post("/image/uploads", response_model=UploadTicketResponse, status_code=201)
async def request_my_image_upload(
    body: ImageUploadRequest, user: ApprovedUser, profiles: ProfilesDep
) -> UploadTicketResponse:
    mentor = await profiles.get_by_user(user.id)
    return _ticket(
        await profiles.request_image_upload(mentor.id, body.content_type, actor_id=user.id)
    )


@me_router.post("/image/uploads/{upload_id}/confirm", response_model=MentorProfileResponse)
async def confirm_my_image(
    upload_id: uuid.UUID, user: ApprovedUser, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    mentor = await profiles.get_by_user(user.id)
    updated = await profiles.confirm_image(mentor.id, upload_id, actor_id=user.id)
    return await _profile(updated, profiles, users)


@me_router.delete("/image", response_model=MentorProfileResponse)
async def delete_my_image(
    user: ApprovedUser, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    mentor = await profiles.get_by_user(user.id)
    return await _profile(await profiles.delete_image(mentor.id, actor_id=user.id), profiles, users)


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[MentorListItem])
async def list_mentors(
    request: Request,
    _: Reader,
    profiles: ProfilesDep,
    users: UsersDep,
    q: Annotated[str | None, Query(max_length=50, description="이름·이메일·휴대폰·닉네임")] = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MentorListItem]:
    summaries, total = await profiles.list_mentors(
        query=q.strip() if q and q.strip() else None,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    found = await users.get_many([s.mentor.user_id for s in summaries])
    reader = cast("MentorCohortReader", request.app.state.mentor_cohorts)
    cohorts = await reader.active_cohorts([s.mentor.id for s in summaries])
    items = []
    for summary in summaries:
        mentor = summary.mentor
        user = found.get(mentor.user_id)
        name = user.name if user else ""
        items.append(
            MentorListItem(
                id=mentor.id,
                user_id=mentor.user_id,
                name=name,
                email=user.email if user else "",
                phone_number=user.phone_number if user else None,
                display_name=display_name(mentor, name),
                is_active=mentor.is_active,
                contract_count=summary.contract_count,
                created_at=mentor.created_at,
                accepting_requests=mentor.accepting_requests,
                active_cohorts=[
                    MentorCohortItem(
                        cohort_id=c.cohort_id,
                        bootcamp_name=c.bootcamp_name,
                        cohort_number=c.cohort_number,
                    )
                    for c in cohorts.get(mentor.id, [])
                ],
            )
        )
    return Page(items=items, total=total, limit=limit, offset=offset)


@admin_router.get("/{mentor_id}/profile", response_model=MentorProfileResponse)
async def get_mentor_profile(
    mentor_id: uuid.UUID, _: Reader, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    return await _profile(await profiles.get(mentor_id), profiles, users)


@admin_router.patch("/{mentor_id}/profile", response_model=MentorProfileResponse)
async def update_mentor_profile(
    mentor_id: uuid.UUID,
    body: ProfileUpdate,
    user: Manager,
    profiles: ProfilesDep,
    users: UsersDep,
) -> MentorProfileResponse:
    updated = await profiles.update(mentor_id, _changes(body), actor_id=user.id)
    return await _profile(updated, profiles, users)


@admin_router.post(
    "/{mentor_id}/profile/image/uploads", response_model=UploadTicketResponse, status_code=201
)
async def request_mentor_image_upload(
    mentor_id: uuid.UUID, body: ImageUploadRequest, user: Manager, profiles: ProfilesDep
) -> UploadTicketResponse:
    return _ticket(
        await profiles.request_image_upload(mentor_id, body.content_type, actor_id=user.id)
    )


@admin_router.post(
    "/{mentor_id}/profile/image/uploads/{upload_id}/confirm",
    response_model=MentorProfileResponse,
)
async def confirm_mentor_image(
    mentor_id: uuid.UUID,
    upload_id: uuid.UUID,
    user: Manager,
    profiles: ProfilesDep,
    users: UsersDep,
) -> MentorProfileResponse:
    updated = await profiles.confirm_image(mentor_id, upload_id, actor_id=user.id)
    return await _profile(updated, profiles, users)


@admin_router.delete("/{mentor_id}/profile/image", response_model=MentorProfileResponse)
async def delete_mentor_image(
    mentor_id: uuid.UUID, user: Manager, profiles: ProfilesDep, users: UsersDep
) -> MentorProfileResponse:
    return await _profile(await profiles.delete_image(mentor_id, actor_id=user.id), profiles, users)

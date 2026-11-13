"""녹화·전사·요약 열람 API (decisions M19·A53·A54, P13-2).

참여자(담당 멘토·1:1 신청 수강생·팀원):
  GET /mentoring/sessions/{id}/artifacts                       목록 (정리 끝난 파일만)
  GET /mentoring/sessions/{id}/artifacts/{artifact_id}/content 중계 (영상 Range, 문서 PDF)
운영진 (mentoring.request.read, 기수 범위):
  GET /admin/cohorts/{cohort_id}/mentoring/sessions/{id}/artifacts[/{artifact_id}/content]
Drive 권한은 아무에게도 주지 않고 백엔드가 서비스 계정으로 중계한다.
"""

import uuid
from datetime import datetime
from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.artifact_service import (
    ArtifactService,
    CohortLabels,
    StudentLookup,
)
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.domain.artifact import MentoringArtifact
from app.contexts.mentoring.domain.enums import MentoringArtifactType
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseMentoringArtifactRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
)
from app.contexts.mentoring.presentation.session_router import get_session_queries
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock
from app.core.meet import build_drive_archive_client
from app.integrations.google.drive import DriveStream

router = APIRouter(prefix="/mentoring/sessions", tags=["mentoring-artifacts"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/sessions", tags=["admin-mentoring-artifacts"]
)

SessionReader = Annotated[
    User, Depends(require_permission("mentoring.request.read", cohort_param="cohort_id"))
]


def get_artifact_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ArtifactService:
    state = request.app.state
    return ArtifactService(
        sessions=TortoiseMentoringSessionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        artifacts=TortoiseMentoringArtifactRepository(),
        access=get_session_queries(request),
        source=None,  # 열람에는 Meet 조회가 필요 없다
        archive=build_drive_archive_client(settings),
        students=cast("StudentLookup", state.student_queries),
        cohorts=cast("CohortLabels", cast("AcademyCatalog", state.academy_catalog)),
        mentors=cast("MentorDirectory", state.mentor_queries),
        users=cast("UserQueries", state.user_queries),
        clock=clock,
    )


ServiceDep = Annotated[ArtifactService, Depends(get_artifact_service)]
RangeHeader = Annotated[str | None, Header(alias="Range")]


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    artifact_type: MentoringArtifactType = Field(description="VIDEO, TRANSCRIPT, SUMMARY")
    file_name: str | None
    mime_type: str = Field(description="받게 될 형식 (문서는 application/pdf)")
    file_size: int | None = Field(description="원본 크기(bytes), 문서는 PDF 크기와 다를 수 있다")
    created_at: datetime | None

    @classmethod
    def of(cls, a: MentoringArtifact) -> "ArtifactResponse":
        return cls(
            id=a.id,
            artifact_type=a.artifact_type,
            file_name=_download_name(a),
            mime_type=a.served_mime_type,
            file_size=a.file_size,
            created_at=a.created_at,
        )


def _download_name(a: MentoringArtifact) -> str | None:
    if a.file_name is None:
        return None
    return (
        f"{a.file_name}.pdf" if a.is_document and not a.file_name.endswith(".pdf") else a.file_name
    )


def _relay(artifact: MentoringArtifact, stream: DriveStream) -> StreamingResponse:
    headers = dict(stream.headers)
    name = _download_name(artifact) or "file"
    headers["content-disposition"] = f"inline; filename*=UTF-8''{quote(name)}"
    headers["cache-control"] = "private, no-store"
    if not artifact.is_document:
        headers.setdefault("accept-ranges", "bytes")
    return StreamingResponse(
        stream.chunks,
        status_code=stream.status_code,
        headers=headers,
        media_type=headers.get("content-type", artifact.served_mime_type),
    )


@router.get("/{session_id}/artifacts", response_model=list[ArtifactResponse])
async def session_artifacts(
    session_id: uuid.UUID, user: ApprovedUser, service: ServiceDep
) -> list[ArtifactResponse]:
    return [ArtifactResponse.of(a) for a in await service.list_for_user(user.id, session_id)]


@router.get("/{session_id}/artifacts/{artifact_id}/content")
async def artifact_content(
    session_id: uuid.UUID,
    artifact_id: uuid.UUID,
    user: ApprovedUser,
    service: ServiceDep,
    range_header: RangeHeader = None,
) -> StreamingResponse:
    """영상은 Range를 그대로 넘겨 206으로, 문서는 PDF로 내보내 중계한다."""
    artifact, stream = await service.open_for_user(user.id, session_id, artifact_id, range_header)
    return _relay(artifact, stream)


@admin_router.get("/{session_id}/artifacts", response_model=list[ArtifactResponse])
async def cohort_session_artifacts(
    cohort_id: uuid.UUID, session_id: uuid.UUID, _: SessionReader, service: ServiceDep
) -> list[ArtifactResponse]:
    return [ArtifactResponse.of(a) for a in await service.list_for_cohort(cohort_id, session_id)]


@admin_router.get("/{session_id}/artifacts/{artifact_id}/content")
async def cohort_artifact_content(
    cohort_id: uuid.UUID,
    session_id: uuid.UUID,
    artifact_id: uuid.UUID,
    _: SessionReader,
    service: ServiceDep,
    range_header: RangeHeader = None,
) -> StreamingResponse:
    artifact, stream = await service.open_for_cohort(
        cohort_id, session_id, artifact_id, range_header
    )
    return _relay(artifact, stream)

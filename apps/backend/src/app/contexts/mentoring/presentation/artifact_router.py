"""녹화·전사·요약 열람 API (decisions M19·A53·A54, P13-2).

참여자(담당 멘토·1:1 신청 수강생·팀원):
  GET  /mentoring/sessions/{id}/artifacts                        목록 (정리 끝난 파일만)
  GET  /mentoring/sessions/{id}/artifacts/{artifact_id}/content  중계 (영상 Range, 문서 PDF)
  POST /mentoring/sessions/{id}/artifacts/{artifact_id}/link     서명 링크 (3시간, A68)
  GET  /mentoring/artifacts/{artifact_id}/stream?token=&download= 서명 링크 중계 (헤더 없이 Range)
  GET  /mentoring/sessions/{id}/artifacts/{artifact_id}/markdown 스마트 메모 마크다운 (A68)
  GET  /mentoring/sessions/{id}/artifacts/{artifact_id}/entries  전사 문장 (A69)
운영진 (mentoring.request.read, 기수 범위):
  GET /admin/cohorts/{cohort_id}/mentoring/sessions/{id}/artifacts[/{artifact_id}/content]
Drive 권한은 아무에게도 주지 않고 백엔드가 서비스 계정으로 중계한다.
"""

import uuid
from datetime import datetime
from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Query, Request
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
    TortoiseTranscriptEntryRepository,
)
from app.contexts.mentoring.presentation.artifact_links import ArtifactGrant, ArtifactLinkSigner
from app.contexts.mentoring.presentation.session_router import get_session_queries
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock
from app.core.meet import build_drive_archive_client
from app.integrations.google.drive import DriveStream

router = APIRouter(prefix="/mentoring/sessions", tags=["mentoring-artifacts"])
link_router = APIRouter(prefix="/mentoring/artifacts", tags=["mentoring-artifacts"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/sessions", tags=["admin-mentoring-artifacts"]
)

SessionReader = Annotated[
    User, Depends(require_permission("mentoring.record.read", cohort_param="cohort_id"))
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
        entries=TortoiseTranscriptEntryRepository(),
    )


ServiceDep = Annotated[ArtifactService, Depends(get_artifact_service)]
RangeHeader = Annotated[str | None, Header(alias="Range")]


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    artifact_type: MentoringArtifactType = Field(description="VIDEO, TRANSCRIPT, SUMMARY")
    file_name: str | None
    mime_type: str = Field(description="받게 될 형식 (문서는 application/pdf)")
    file_size: int | None = Field(description="원본 크기(bytes), 문서는 PDF 크기와 다를 수 있다")
    conference_record: str | None = Field(
        description="Meet 회의 기록 이름. 같은 값의 영상·전사본이 한 회의다 (A69)"
    )
    started_at: datetime | None = Field(
        description="녹화 시작(영상만). 전사 문장 시각 − 이 값 = 영상 위치 (A69)"
    )
    ended_at: datetime | None = Field(
        description="녹화 끝(영상만). 녹화 고르기에 시작~끝을 보여 준다 (A71)"
    )
    created_at: datetime | None

    @classmethod
    def of(cls, a: MentoringArtifact) -> "ArtifactResponse":
        return cls(
            id=a.id,
            artifact_type=a.artifact_type,
            file_name=_download_name(a),
            mime_type=a.served_mime_type,
            file_size=a.file_size,
            conference_record=a.conference_record,
            started_at=a.started_at,
            ended_at=a.ended_at,
            created_at=a.created_at,
        )


def _download_name(a: MentoringArtifact) -> str | None:
    if a.file_name is None:
        return None
    return (
        f"{a.file_name}.pdf" if a.is_document and not a.file_name.endswith(".pdf") else a.file_name
    )


class ArtifactLinkResponse(BaseModel):
    url: str = Field(description="API 기준 경로 + 서명 토큰. <video src>·내려받기에 그대로 쓴다")
    download_url: str = Field(description="같은 링크의 내려받기(attachment) 버전")
    expires_at: datetime


class ArtifactMarkdownResponse(BaseModel):
    artifact_id: uuid.UUID
    markdown: str = Field(
        description="스마트 메모를 Drive에서 마크다운으로 내보낸 원문 (저장 안 함)"
    )


def get_link_signer(settings: Annotated[Settings, Depends(get_app_settings)]) -> ArtifactLinkSigner:
    return ArtifactLinkSigner(settings)


SignerDep = Annotated[ArtifactLinkSigner, Depends(get_link_signer)]


def _relay(
    artifact: MentoringArtifact, stream: DriveStream, *, download: bool = False
) -> StreamingResponse:
    headers = dict(stream.headers)
    name = _download_name(artifact) or "file"
    disposition = "attachment" if download else "inline"
    headers["content-disposition"] = f"{disposition}; filename*=UTF-8''{quote(name)}"
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


@router.post("/{session_id}/artifacts/{artifact_id}/link", response_model=ArtifactLinkResponse)
async def artifact_link(
    session_id: uuid.UUID,
    artifact_id: uuid.UUID,
    user: ApprovedUser,
    service: ServiceDep,
    signer: SignerDep,
    clock: Annotated[Clock, Depends(get_clock)],
) -> ArtifactLinkResponse:
    """참여자만. 그 파일·그 사용자에 묶인 3시간짜리 서명 링크 (A68)."""
    await service.viewable_for_user(user.id, session_id, artifact_id)
    token, expires_at = signer.sign(
        ArtifactGrant(user_id=user.id, session_id=session_id, artifact_id=artifact_id),
        now=clock.now(),
    )
    path = f"/api/v1/mentoring/artifacts/{artifact_id}/stream?token={quote(token)}"
    return ArtifactLinkResponse(url=path, download_url=f"{path}&download=1", expires_at=expires_at)


@link_router.get("/{artifact_id}/stream")
async def artifact_stream(
    artifact_id: uuid.UUID,
    signer: SignerDep,
    service: ServiceDep,
    token: Annotated[str, Query(description="서명 링크의 토큰")],
    download: Annotated[bool, Query(description="참이면 내려받기(attachment)")] = False,
    range_header: RangeHeader = None,
) -> StreamingResponse:
    """서명 링크 중계: 헤더 없이 Range를 받고, 매번 참여자인지 다시 확인한다 (A68)."""
    grant = signer.verify(token, artifact_id)
    artifact, stream = await service.open_for_user(
        grant.user_id, grant.session_id, artifact_id, range_header
    )
    return _relay(artifact, stream, download=download)


class TranscriptEntryResponse(BaseModel):
    sequence: int
    speaker_name: str = Field(description="서비스 이름으로 바꾼 화자 (모르면 Meet 표시 이름, A69)")
    text: str
    started_at: datetime
    ended_at: datetime | None


@router.get(
    "/{session_id}/artifacts/{artifact_id}/entries", response_model=list[TranscriptEntryResponse]
)
async def transcript_entries(
    session_id: uuid.UUID, artifact_id: uuid.UUID, user: ApprovedUser, service: ServiceDep
) -> list[TranscriptEntryResponse]:
    """참여자만. 전사본(TRANSCRIPT)의 문장을 순서대로 (A68·A69). 아직 못 받았으면 빈 목록."""
    return [
        TranscriptEntryResponse(
            sequence=e.sequence,
            speaker_name=e.speaker_name,
            text=e.text,
            started_at=e.started_at,
            ended_at=e.ended_at,
        )
        for e in await service.entries_for_user(user.id, session_id, artifact_id)
    ]


@router.get(
    "/{session_id}/artifacts/{artifact_id}/markdown", response_model=ArtifactMarkdownResponse
)
async def artifact_markdown(
    session_id: uuid.UUID, artifact_id: uuid.UUID, user: ApprovedUser, service: ServiceDep
) -> ArtifactMarkdownResponse:
    """참여자만. 스마트 메모(SUMMARY)를 마크다운으로 (A68). 다른 종류는 404 artifact_not_found."""
    artifact, markdown = await service.markdown_for_user(user.id, session_id, artifact_id)
    return ArtifactMarkdownResponse(artifact_id=artifact.id, markdown=markdown)


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

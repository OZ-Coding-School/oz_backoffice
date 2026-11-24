"""세션 기록·내부 메모 API (decisions M22·M27·M28·A53, P13-1).

멘토(담당 멘토만):
  POST  /mentoring/sessions/{id}/record     기록 제출 (완료: 진행 시간·주제·요약 / 노쇼: 사유 선택)
  PATCH /mentoring/sessions/{id}/record     주제·요약 수정 (제출 후 7일)
  GET   /mentoring/sessions/{id}/note       내부 메모 조회
  PUT   /mentoring/sessions/{id}/note       내부 메모 저장 (작성·수정)
운영진 (mentoring.request.read, 기수 범위, 조회만):
  GET   /admin/cohorts/{cohort_id}/mentoring/sessions/unrecorded      기록 미제출 세션
  GET   /admin/cohorts/{cohort_id}/mentoring/sessions/{id}/note       내부 메모
세션 라우터의 `/{session_id}`보다 먼저 등록해야 `unrecorded`가 세션 ID로 해석되지 않는다.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.record_service import (
    RecordInput,
    SessionRecordService,
    StudentLookup,
)
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.note import NOTE_MAX_LENGTH, MentoringSessionNote
from app.contexts.mentoring.domain.session import SUMMARY_MAX_LENGTH, TOPIC_MAX_LENGTH
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionNoteRepository,
    TortoiseMentoringSessionRepository,
)
from app.contexts.mentoring.presentation.notices import build_notices
from app.contexts.mentoring.presentation.session_router import (
    AdminSessionResponse,
    SessionPresenter,
    SessionResponse,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.pagination import Page
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/mentoring/sessions", tags=["mentoring-records"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/sessions", tags=["admin-mentoring-records"]
)

SessionReader = Annotated[
    User, Depends(require_permission("mentoring.record.read", cohort_param="cohort_id"))
]


def get_record_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> SessionRecordService:
    state = request.app.state
    return SessionRecordService(
        sessions=TortoiseMentoringSessionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        notes=TortoiseMentoringSessionNoteRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        notices=build_notices(request, clock),
    )


ServiceDep = Annotated[SessionRecordService, Depends(get_record_service)]
PresenterDep = Annotated[SessionPresenter, Depends(SessionPresenter)]


class RecordBody(BaseModel):
    status: Literal[MentoringSessionStatus.COMPLETED, MentoringSessionStatus.NO_SHOW]
    duration: int | None = Field(
        default=None, gt=0, description="실제 진행 시간(분, 30분 단위), 완료만"
    )
    topic: str | None = Field(
        default=None, max_length=TOPIC_MAX_LENGTH, description="완료만, 없으면 신청 주제"
    )
    summary: str | None = Field(
        default=None,
        max_length=SUMMARY_MAX_LENGTH,
        description="완료는 요약(필수), 노쇼는 사유(선택)",
    )

    @model_validator(mode="after")
    def _completed_needs_duration(self) -> Self:
        if self.status is MentoringSessionStatus.COMPLETED and self.duration is None:
            raise ValueError("완료 기록에는 진행 시간이 필요합니다.")
        return self


class RecordEdit(BaseModel):
    topic: str | None = Field(default=None, max_length=TOPIC_MAX_LENGTH)
    summary: str | None = Field(default=None, max_length=SUMMARY_MAX_LENGTH)


class NoteBody(BaseModel):
    body: str = Field(min_length=1, max_length=NOTE_MAX_LENGTH)


class NoteResponse(BaseModel):
    session_id: uuid.UUID
    body: str | None = Field(description="아직 작성하지 않았으면 null")
    updated_at: datetime | None

    @classmethod
    def of(cls, session_id: uuid.UUID, note: MentoringSessionNote | None) -> "NoteResponse":
        return cls(
            session_id=session_id,
            body=note.body if note else None,
            updated_at=note.updated_at if note else None,
        )


# ---------------------------------------------------------------- 멘토
@router.post("/{session_id}/record", response_model=SessionResponse)
async def submit_record(
    session_id: uuid.UUID,
    body: RecordBody,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> SessionResponse:
    """진행 시간·완료/노쇼는 처음 제출로 고정. 계좌는 실제 진행 시간 기준으로 맞춘다."""
    session = await service.submit(
        user.id,
        session_id,
        RecordInput(
            status=MentoringSessionStatus(body.status),
            summary=body.summary,
            duration=body.duration,
            topic=body.topic,
        ),
    )
    return (await presenter.public([session]))[0]


@router.patch("/{session_id}/record", response_model=SessionResponse)
async def edit_record(
    session_id: uuid.UUID,
    body: RecordEdit,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> SessionResponse:
    session = await service.edit(user.id, session_id, topic=body.topic, summary=body.summary)
    return (await presenter.public([session]))[0]


@router.get("/{session_id}/note", response_model=NoteResponse)
async def my_note(session_id: uuid.UUID, user: ApprovedUser, service: ServiceDep) -> NoteResponse:
    return NoteResponse.of(session_id, await service.my_note(user.id, session_id))


@router.put("/{session_id}/note", response_model=NoteResponse)
async def write_note(
    session_id: uuid.UUID, body: NoteBody, user: ApprovedUser, service: ServiceDep
) -> NoteResponse:
    return NoteResponse.of(session_id, await service.write_note(user.id, session_id, body.body))


# ---------------------------------------------------------------- 운영진
@admin_router.get("/unrecorded", response_model=Page[AdminSessionResponse])
async def unrecorded_sessions(
    cohort_id: uuid.UUID,
    _: SessionReader,
    service: ServiceDep,
    presenter: PresenterDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminSessionResponse]:
    """예정 시작이 지났는데 기록이 없는 세션 (시작 오래된 순)."""
    items, total = await service.unrecorded(cohort_id, limit=limit, offset=offset)
    return Page(items=await presenter.admin(items), total=total, limit=limit, offset=offset)


@admin_router.get("/{session_id}/note", response_model=NoteResponse)
async def cohort_note(
    cohort_id: uuid.UUID, session_id: uuid.UUID, _: SessionReader, service: ServiceDep
) -> NoteResponse:
    return NoteResponse.of(session_id, await service.cohort_note(cohort_id, session_id))

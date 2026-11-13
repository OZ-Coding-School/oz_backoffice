"""멘토링 정산 API — 운영진 (decisions M16·A55, P14-1).

권한 `mentoring.settlement.close`(기수 범위).

POST /admin/cohorts/{cohort_id}/mentoring/settlements/aggregate   {month: "YYYY-MM"} 집계(다시 집계)
GET  /admin/cohorts/{cohort_id}/mentoring/settlements?month=      목록
GET  /admin/cohorts/{cohort_id}/mentoring/settlements/{id}        상세(명세)
POST /admin/cohorts/{cohort_id}/mentoring/settlements/{id}/close  {confirm} 마감
"""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.settlement_service import SettlementService
from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.settlement import MentoringSettlement
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentorRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringSettlementRepository,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork

admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/settlements", tags=["admin-mentoring-settlements"]
)

SettlementManager = Annotated[
    User, Depends(require_permission("mentoring.settlement.close", cohort_param="cohort_id"))
]
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _parse_month(value: str) -> date:
    if not MONTH.match(value):
        raise ValueError("월은 YYYY-MM 형식입니다.")
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def get_settlement_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> SettlementService:
    return SettlementService(
        settlements=TortoiseMentoringSettlementRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        assignments=TortoiseCohortMentorRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


ServiceDep = Annotated[SettlementService, Depends(get_settlement_service)]


class MonthBody(BaseModel):
    month: str = Field(description="YYYY-MM (KST)", examples=["2026-11"])

    @field_validator("month")
    @classmethod
    def _valid(cls, value: str) -> str:
        _parse_month(value)
        return value


class CloseBody(BaseModel):
    confirm: bool = Field(default=False, description="기록 미제출 세션이 있어도 마감한다")


class SettlementSummary(BaseModel):
    id: uuid.UUID
    mentor_id: uuid.UUID
    mentor_name: str
    cohort_id: uuid.UUID
    month: str = Field(description="YYYY-MM")
    status: MentoringSettlementStatus
    session_count: int
    total_minutes: int
    total_amount: int = Field(description="원")
    closed_at: datetime | None


class SettlementItemResponse(BaseModel):
    session_id: uuid.UUID
    session_starts_at: datetime | None
    item_type: SettlementItemType
    settlement_policy: MentoringSettlementPolicy
    billable_minutes: int
    pay_unit: PayUnit
    pay_rate: int
    amount: int


class SettlementDetail(SettlementSummary):
    items: list[SettlementItemResponse]


class SkippedResponse(BaseModel):
    session_id: uuid.UUID
    code: str = Field(description="assignment_not_found: 세션 시작일에 유효한 배정이 없음")


class AggregateResponse(BaseModel):
    settlements: list[SettlementSummary]
    skipped: list[SkippedResponse]
    closed: list[uuid.UUID] = Field(description="이미 마감돼 다시 집계하지 않은 정산")


class UnrecordedResponse(BaseModel):
    session_id: uuid.UUID
    starts_at: datetime
    title: str


class CloseResponse(BaseModel):
    applied: bool = Field(description="false면 기록 미제출 세션이 있어 확인(confirm=true) 필요")
    settlement: SettlementSummary
    unrecorded: list[UnrecordedResponse]


class Presenter:
    def __init__(self, request: Request) -> None:
        state = request.app.state
        self._mentors = cast("MentorDirectory", state.mentor_queries)
        self._users = cast("UserQueries", state.user_queries)
        self._sessions = TortoiseMentoringSessionRepository()

    async def _names(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        mentors = await self._mentors.get_many(list(set(mentor_ids)))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        return {
            m.id: (users[m.user_id].name if m.user_id in users else "") for m in mentors.values()
        }

    @staticmethod
    def _summary(s: MentoringSettlement, name: str) -> SettlementSummary:
        return SettlementSummary(
            id=s.id,
            mentor_id=s.mentor_id,
            mentor_name=name,
            cohort_id=s.cohort_id,
            month=s.settlement_month.strftime("%Y-%m"),
            status=s.status,
            session_count=s.session_count,
            total_minutes=s.total_minutes,
            total_amount=s.total_amount,
            closed_at=s.closed_at,
        )

    async def summaries(self, items: list[MentoringSettlement]) -> list[SettlementSummary]:
        names = await self._names([s.mentor_id for s in items])
        return [self._summary(s, names.get(s.mentor_id, "")) for s in items]

    async def detail(self, s: MentoringSettlement) -> SettlementDetail:
        names = await self._names([s.mentor_id])
        sessions = await self._sessions.get_many([i.session_id for i in s.items])
        return SettlementDetail(
            **self._summary(s, names.get(s.mentor_id, "")).model_dump(),
            items=[
                SettlementItemResponse(
                    session_id=i.session_id,
                    session_starts_at=sessions[i.session_id].starts_at
                    if i.session_id in sessions
                    else None,
                    item_type=i.item_type,
                    settlement_policy=i.settlement_policy,
                    billable_minutes=i.billable_minutes,
                    pay_unit=i.pay_unit,
                    pay_rate=i.pay_rate,
                    amount=i.amount,
                )
                for i in sorted(
                    s.items,
                    key=lambda i: (
                        sessions[i.session_id].starts_at
                        if i.session_id in sessions
                        else datetime.min.replace(tzinfo=None)
                    ),
                )
            ],
        )

    @staticmethod
    def unrecorded(items: list[MentoringSession]) -> list[UnrecordedResponse]:
        return [
            UnrecordedResponse(session_id=s.id, starts_at=s.starts_at, title=s.title) for s in items
        ]


PresenterDep = Annotated[Presenter, Depends(Presenter)]


@admin_router.post("/aggregate", response_model=AggregateResponse)
async def aggregate(
    cohort_id: uuid.UUID,
    body: MonthBody,
    user: SettlementManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AggregateResponse:
    """그 달 말까지 기록된, 아직 정산되지 않은 세션을 멘토별로 모은다 (DRAFT 다시 계산)."""
    result = await service.aggregate(cohort_id, _parse_month(body.month), actor_id=user.id)
    return AggregateResponse(
        settlements=await presenter.summaries(result.settlements),
        skipped=[SkippedResponse(session_id=s.session_id, code=s.code) for s in result.skipped],
        closed=[s.id for s in result.closed],
    )


@admin_router.get("", response_model=list[SettlementSummary])
async def list_settlements(
    cohort_id: uuid.UUID,
    _: SettlementManager,
    service: ServiceDep,
    presenter: PresenterDep,
    month: Annotated[str | None, Query(pattern=MONTH.pattern, description="YYYY-MM")] = None,
) -> list[SettlementSummary]:
    items = await service.list_by_cohort(cohort_id, month=_parse_month(month) if month else None)
    return await presenter.summaries(items)


@admin_router.get("/{settlement_id}", response_model=SettlementDetail)
async def get_settlement(
    cohort_id: uuid.UUID,
    settlement_id: uuid.UUID,
    _: SettlementManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> SettlementDetail:
    return await presenter.detail(await service.get(cohort_id, settlement_id))


@admin_router.post("/{settlement_id}/close", response_model=CloseResponse)
async def close_settlement(
    cohort_id: uuid.UUID,
    settlement_id: uuid.UUID,
    body: CloseBody,
    user: SettlementManager,
    service: ServiceDep,
    presenter: PresenterDep,
) -> CloseResponse:
    result = await service.close(cohort_id, settlement_id, confirm=body.confirm, actor_id=user.id)
    (summary,) = await presenter.summaries([result.settlement])
    return CloseResponse(
        applied=result.applied,
        settlement=summary,
        unrecorded=presenter.unrecorded(result.unrecorded),
    )

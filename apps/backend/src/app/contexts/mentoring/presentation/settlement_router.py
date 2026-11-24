"""멘토링 정산 API — 운영진 (decisions M16·A55, P14-1).

권한 `mentoring.settlement.close`(기수 범위).

POST /admin/cohorts/{cohort_id}/mentoring/settlements/aggregate   {month: "YYYY-MM"} 집계(다시 집계)
GET  /admin/cohorts/{cohort_id}/mentoring/settlements?month=      목록
GET  /admin/cohorts/{cohort_id}/mentoring/settlements/{id}        상세(명세)
POST /admin/cohorts/{cohort_id}/mentoring/settlements/{id}/close  {confirm} 마감
"""

import csv
import io
import re
import uuid
from datetime import date, datetime
from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.settlement_export import (
    OPTIONAL_COLUMNS,
    CohortLabels,
    SettlementExporter,
    header,
)
from app.contexts.mentoring.application.settlement_export import (
    StudentLookup as ExportStudents,
)
from app.contexts.mentoring.application.settlement_service import SettlementService
from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.settlement import MentoringSettlement, SettlementItem
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentorRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringSettlementRepository,
    TortoiseMentoringTeamRepository,
)
from app.contexts.mentoring.presentation.presenters import NameBook
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation

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
        mentors=cast("MentorDirectory", request.app.state.mentor_queries),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


ServiceDep = Annotated[SettlementService, Depends(get_settlement_service)]
me_router = APIRouter(prefix="/me/mentor-settlements", tags=["mentor-settlements"])


def get_exporter(request: Request) -> SettlementExporter:
    state = request.app.state
    return SettlementExporter(
        sessions=TortoiseMentoringSessionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        teams=TortoiseMentoringTeamRepository(),
        students=cast("ExportStudents", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        users=cast("UserQueries", state.user_queries),
        cohorts=cast("CohortLabels", state.academy_catalog),
    )


ExporterDep = Annotated[SettlementExporter, Depends(get_exporter)]


def _columns(value: str | None) -> list[str]:
    picked = [c.strip() for c in (value or "").split(",") if c.strip()]
    unknown = [c for c in picked if c not in OPTIONAL_COLUMNS]
    if unknown:
        raise BusinessRuleViolation(
            f"알 수 없는 열입니다: {', '.join(unknown)} (가능: {', '.join(OPTIONAL_COLUMNS)})",
            code="invalid_export_columns",
        )
    return list(dict.fromkeys(picked))


ColumnsQuery = Annotated[
    str | None,
    Query(description="선택 열, 쉼표 구분: " + ", ".join(OPTIONAL_COLUMNS)),
]


def _csv_response(rows: list[list[str]], columns: list[str], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header(columns))
    writer.writerows(rows)
    body = "\ufeff" + buffer.getvalue()  # 엑셀이 UTF-8로 읽도록 BOM
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "cache-control": "private, no-store",
        },
    )


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
    bootcamp_name: str | None = Field(description="기수의 과정명 (A80)")
    cohort_number: int | None = Field(description="기수 번호 (A80)")
    month: str = Field(description="YYYY-MM")
    status: MentoringSettlementStatus
    session_count: int
    total_minutes: int
    total_amount: int = Field(description="원")
    closed_at: datetime | None


class SettlementItemResponse(BaseModel):
    session_id: uuid.UUID
    session_starts_at: datetime | None
    session_topic: str | None = Field(description="세션 주제 (A80)")
    team_label: str | None = Field(description="팀 멘토링이면 팀 이름 (A80)")
    requester_name: str | None = Field(description="신청자 이름. 1:1 상대 (A80)")
    item_type: SettlementItemType
    settlement_policy: MentoringSettlementPolicy
    billable_minutes: int
    pay_unit: PayUnit
    pay_rate: int
    amount: int
    uncharged_overtime_minutes: int | None = Field(
        description="잔여가 모자라 차감하지 못한 초과 진행 시간(분), 정산 참고 (A78)"
    )


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
        self._requests = TortoiseMentoringRequestRepository()
        self._book = NameBook(request)

    async def _names(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        mentors = await self._mentors.get_many(list(set(mentor_ids)))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        return {
            m.id: (users[m.user_id].name if m.user_id in users else "") for m in mentors.values()
        }

    @staticmethod
    def _summary(
        s: MentoringSettlement, name: str, label: tuple[str, int] | None
    ) -> SettlementSummary:
        return SettlementSummary(
            id=s.id,
            mentor_id=s.mentor_id,
            mentor_name=name,
            cohort_id=s.cohort_id,
            bootcamp_name=label[0] if label else None,
            cohort_number=label[1] if label else None,
            month=s.settlement_month.strftime("%Y-%m"),
            status=s.status,
            session_count=s.session_count,
            total_minutes=s.total_minutes,
            total_amount=s.total_amount,
            closed_at=s.closed_at,
        )

    async def summaries(self, items: list[MentoringSettlement]) -> list[SettlementSummary]:
        names = await self._names([s.mentor_id for s in items])
        labels = await self._book.cohort_labels(list({s.cohort_id for s in items}))
        return [
            self._summary(s, names.get(s.mentor_id, ""), labels.get(s.cohort_id)) for s in items
        ]

    async def detail(self, s: MentoringSettlement) -> SettlementDetail:
        names = await self._names([s.mentor_id])
        labels = await self._book.cohort_labels([s.cohort_id])
        sessions = await self._sessions.get_many([i.session_id for i in s.items])
        requests = await self._requests.get_many(list({x.request_id for x in sessions.values()}))
        people = await self._book.of(list(requests.values()))

        def item(i: SettlementItem) -> SettlementItemResponse:
            session = sessions.get(i.session_id)
            who = people.get(session.request_id) if session else None
            return SettlementItemResponse(
                session_id=i.session_id,
                session_starts_at=session.starts_at if session else None,
                session_topic=session.topic if session else None,
                team_label=who.team_label if who else None,
                requester_name=who.requester_name if who else None,
                item_type=i.item_type,
                settlement_policy=i.settlement_policy,
                billable_minutes=i.billable_minutes,
                pay_unit=i.pay_unit,
                pay_rate=i.pay_rate,
                amount=i.amount,
                uncharged_overtime_minutes=session.uncharged_overtime_minutes if session else None,
            )

        ordered = sorted(
            s.items,
            key=lambda i: (
                sessions[i.session_id].starts_at
                if i.session_id in sessions
                else datetime.min.replace(tzinfo=None)
            ),
        )
        return SettlementDetail(
            **self._summary(s, names.get(s.mentor_id, ""), labels.get(s.cohort_id)).model_dump(),
            items=[item(i) for i in ordered],
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


@admin_router.get("/export.csv", response_class=Response)
async def export_cohort_month(
    cohort_id: uuid.UUID,
    _: SettlementManager,
    service: ServiceDep,
    exporter: ExporterDep,
    month: Annotated[str, Query(pattern=MONTH.pattern, description="YYYY-MM")],
    columns: ColumnsQuery = None,
) -> Response:
    """그 기수·월의 모든 정산서 명세 (집계 중·마감 모두, 정산 상태 열로 구분)."""
    picked = _columns(columns)
    settlements = await service.list_by_cohort(
        cohort_id, month=_parse_month(month), with_items=True
    )
    rows = await exporter.rows(settlements, picked)
    return _csv_response(rows, picked, f"멘토링정산_{month}.csv")


@admin_router.get("/{settlement_id}/export.csv", response_class=Response)
async def export_settlement(
    cohort_id: uuid.UUID,
    settlement_id: uuid.UUID,
    _: SettlementManager,
    service: ServiceDep,
    exporter: ExporterDep,
    presenter: PresenterDep,
    columns: ColumnsQuery = None,
) -> Response:
    picked = _columns(columns)
    settlement = await service.get(cohort_id, settlement_id)
    rows = await exporter.rows([settlement], picked)
    (summary,) = await presenter.summaries([settlement])
    name = f"멘토링정산_{summary.month}_{summary.mentor_name or settlement.mentor_id}.csv"
    return _csv_response(rows, picked, name)


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


# ---------------------------------------------------------------- 멘토 본인
@me_router.get("", response_model=list[SettlementSummary])
async def my_settlements(
    user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> list[SettlementSummary]:
    """마감된 정산만 (A55)."""
    return await presenter.summaries(await service.list_for_mentor(user.id))


@me_router.get("/{settlement_id}", response_model=SettlementDetail)
async def my_settlement(
    settlement_id: uuid.UUID, user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> SettlementDetail:
    return await presenter.detail(await service.get_for_mentor(user.id, settlement_id))

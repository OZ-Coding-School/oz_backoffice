"""기수 멘토링 설정·금지 시간대·추가 휴일 API (decisions A34). 권한: mentoring.settings.manage.

GET/PUT          /admin/cohorts/{cohort_id}/mentoring-settings           (기수 범위)
GET/POST         /admin/cohorts/{cohort_id}/mentoring-block-times        (기수 범위)
PATCH/DELETE     /admin/cohorts/{cohort_id}/mentoring-block-times/{id}   (기수 범위)
GET              /admin/mentoring-holidays?year=                         (법정공휴일 + 추가 휴일)
POST             /admin/mentoring-holidays/sync                          (올해·내년 법정공휴일, A95)
POST / DELETE    /admin/mentoring-holidays[/{id}]                        (추가 휴일, 담당 범위 필요)

GET              /mentoring/holidays?from=&to=                (로그인한 누구나, 달력 참고, A107)
"""

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal, cast

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import CurrentUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.calendar import BusinessCalendar, HolidaySource
from app.contexts.mentoring.application.holiday_sync import PublicHolidaySyncService
from app.contexts.mentoring.application.settings_service import (
    CohortDirectory,
    MentoringSettingsService,
)
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
    OperatingHours,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringBlockTimeRepository,
    TortoiseMentoringHolidayRepository,
    TortoisePublicHolidayRepository,
)
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock, get_http_client
from app.core.holidays import build_holiday_source
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ServiceUnavailableError

router = APIRouter(prefix="/admin", tags=["admin-mentoring-settings"])
calendar_router = APIRouter(prefix="/mentoring", tags=["mentoring-calendar"])

# 달력 한 화면(6주)보다 넉넉히
CALENDAR_MAX_DAYS = 100

READ = "mentoring.settings.read"
MANAGE = "mentoring.settings.manage"
CohortManager = Annotated[User, Depends(require_permission(MANAGE, cohort_param="cohort_id"))]
CohortReader = Annotated[User, Depends(require_permission(READ, cohort_param="cohort_id"))]
AnyManager = Annotated[User, Depends(require_permission(MANAGE, any_scope=True))]
AnyReader = Annotated[User, Depends(require_permission(READ, any_scope=True))]


def get_settings_service(request: Request) -> MentoringSettingsService:
    return MentoringSettingsService(
        settings=TortoiseCohortMentoringSettingsRepository(),
        blocks=TortoiseMentoringBlockTimeRepository(),
        holidays=TortoiseMentoringHolidayRepository(),
        cohorts=cast("CohortDirectory", request.app.state.academy_catalog),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )


ServiceDep = Annotated[MentoringSettingsService, Depends(get_settings_service)]


def get_holiday_sync_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> PublicHolidaySyncService:
    source = build_holiday_source(settings, http)
    if source is None:
        raise ServiceUnavailableError(
            "공휴일 정보 연동이 설정되지 않았습니다.", code="holiday_sync_failed"
        )
    return PublicHolidaySyncService(
        source=source, holidays=TortoisePublicHolidayRepository(), uow=UnitOfWork(), clock=clock
    )


SyncServiceDep = Annotated[PublicHolidaySyncService, Depends(get_holiday_sync_service)]


# ---------------------------------------------------------------- 스키마
class HoursBody(BaseModel):
    """운영시간 (한국 시각, 정각·30분, 끝은 24:00까지)."""

    start: str = Field(pattern=r"^\d{2}:\d{2}$", examples=["10:00"])
    end: str = Field(pattern=r"^\d{2}:\d{2}$", examples=["19:00"])

    def to_hours(self) -> OperatingHours:
        return OperatingHours.of(self.start, self.end)

    @classmethod
    def of(cls, hours: OperatingHours | None) -> "HoursBody | None":
        if hours is None:
            return None
        return cls(
            start=OperatingHours.label(hours.start_minute),
            end=OperatingHours.label(hours.end_minute),
        )


class SettingsFields(BaseModel):
    """설정 전체 (PUT). 값 제한은 서비스·DB가 검사한다."""

    allow_team_mentoring: bool = False
    allow_1_on_1: bool = False
    default_1on1_minutes: int = Field(default=0, ge=0, description="60분 단위")
    default_team_minutes: int = Field(default=0, ge=0, description="60분 단위")
    min_lead_hours: Literal[6, 12, 24] = 24
    allowed_duration: Literal[30, 60] = 30
    max_pending_requests: int = Field(default=1, ge=1, le=3)
    weekday_hours: HoursBody | None = Field(
        default_factory=lambda: HoursBody(start="10:00", end="19:00"),
        description="평일 운영시간 (null = 운영 안 함). 수강생은 이 시간 안에서만 신청한다 (A37)",
    )
    weekend_hours: HoursBody | None = Field(
        default=None, description="주말·공휴일 운영시간 (null = 운영 안 함)"
    )

    def to_values(self) -> dict[str, object]:
        values = self.model_dump(exclude={"weekday_hours", "weekend_hours"})
        values["weekday_hours"] = self.weekday_hours.to_hours() if self.weekday_hours else None
        values["weekend_hours"] = self.weekend_hours.to_hours() if self.weekend_hours else None
        return values


class SettingsResponse(SettingsFields):
    cohort_id: uuid.UUID
    updated_at: datetime | None

    @classmethod
    def of(cls, s: CohortMentoringSettings) -> "SettingsResponse":
        return cls(
            cohort_id=s.cohort_id,
            allow_team_mentoring=s.allow_team_mentoring,
            allow_1_on_1=s.allow_1_on_1,
            default_1on1_minutes=s.default_1on1_minutes,
            default_team_minutes=s.default_team_minutes,
            min_lead_hours=cast("Literal[6, 12, 24]", s.min_lead_hours),
            allowed_duration=cast("Literal[30, 60]", s.allowed_duration),
            max_pending_requests=s.max_pending_requests,
            weekday_hours=HoursBody.of(s.weekday_hours),
            weekend_hours=HoursBody.of(s.weekend_hours),
            updated_at=s.updated_at,
        )


class BlockTimeFields(BaseModel):
    period_start: date
    period_end: date
    start_time: time = Field(description="한국 시각 (예: 09:00)")
    end_time: time
    reason: str | None = Field(default=None, max_length=200)


class BlockTimeUpdate(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    reason: str | None = Field(default=None, max_length=200)


class BlockTimeResponse(BlockTimeFields):
    id: uuid.UUID
    cohort_id: uuid.UUID
    weekdays_only: bool = Field(
        default=True, description="평일(월~금)에만 적용, 주말·공휴일 제외 (A34)"
    )

    @classmethod
    def of(cls, b: MentoringBlockTime) -> "BlockTimeResponse":
        return cls(
            id=b.id,
            cohort_id=b.cohort_id,
            period_start=b.period_start,
            period_end=b.period_end,
            start_time=b.start_time,
            end_time=b.end_time,
            reason=b.reason,
        )


class HolidayCreate(BaseModel):
    holiday_date: date
    name: str = Field(min_length=1, max_length=50)


class HolidayResponse(BaseModel):
    id: uuid.UUID | None = Field(description="추가 휴일만 (법정공휴일은 null)")
    holiday_date: date
    name: str
    source: HolidaySource

    @classmethod
    def custom(cls, h: MentoringHoliday) -> "HolidayResponse":
        return cls(id=h.id, holiday_date=h.holiday_date, name=h.name, source=HolidaySource.CUSTOM)


class HolidayListResponse(BaseModel):
    items: list[HolidayResponse]
    synced_at: datetime | None = Field(
        description="그해 법정공휴일 마지막 동기화 시각 (null이면 아직 받지 않은 해)"
    )


class HolidaySyncYear(BaseModel):
    year: int
    synced_at: datetime
    holiday_count: int


class HolidaySyncResponse(BaseModel):
    years: list[HolidaySyncYear]


# ---------------------------------------------------------------- 설정
@router.get("/cohorts/{cohort_id}/mentoring-settings", response_model=SettingsResponse)
async def get_settings(
    cohort_id: uuid.UUID, _: CohortReader, service: ServiceDep
) -> SettingsResponse:
    """설정이 없으면 404 `mentoring_settings_not_configured` (설정 페이지로 안내)."""
    return SettingsResponse.of(await service.get_settings(cohort_id))


@router.put("/cohorts/{cohort_id}/mentoring-settings", response_model=SettingsResponse)
async def save_settings(
    cohort_id: uuid.UUID, body: SettingsFields, user: CohortManager, service: ServiceDep
) -> SettingsResponse:
    """설정 전체 저장(없으면 생성). 진행 중인 신청에는 소급하지 않는다."""
    saved = await service.save_settings(cohort_id, body.to_values(), actor_id=user.id)
    return SettingsResponse.of(saved)


# ---------------------------------------------------------------- 금지 시간대
@router.get("/cohorts/{cohort_id}/mentoring-block-times", response_model=list[BlockTimeResponse])
async def list_block_times(
    cohort_id: uuid.UUID, _: CohortReader, service: ServiceDep
) -> list[BlockTimeResponse]:
    return [BlockTimeResponse.of(b) for b in await service.list_blocks(cohort_id)]


@router.post(
    "/cohorts/{cohort_id}/mentoring-block-times",
    response_model=BlockTimeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_block_time(
    cohort_id: uuid.UUID, body: BlockTimeFields, user: CohortManager, service: ServiceDep
) -> BlockTimeResponse:
    block = await service.create_block(cohort_id, body.model_dump(), actor_id=user.id)
    return BlockTimeResponse.of(block)


@router.patch(
    "/cohorts/{cohort_id}/mentoring-block-times/{block_id}", response_model=BlockTimeResponse
)
async def update_block_time(
    cohort_id: uuid.UUID,
    block_id: uuid.UUID,
    body: BlockTimeUpdate,
    user: CohortManager,
    service: ServiceDep,
) -> BlockTimeResponse:
    changes = body.model_dump(exclude_unset=True)
    changes = {k: v for k, v in changes.items() if v is not None or k == "reason"}
    block = await service.update_block(cohort_id, block_id, changes, actor_id=user.id)
    return BlockTimeResponse.of(block)


@router.delete(
    "/cohorts/{cohort_id}/mentoring-block-times/{block_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_block_time(
    cohort_id: uuid.UUID, block_id: uuid.UUID, user: CohortManager, service: ServiceDep
) -> Response:
    await service.delete_block(cohort_id, block_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 휴일
@router.get("/mentoring-holidays", response_model=HolidayListResponse)
async def list_holidays(
    _: AnyReader,
    year: Annotated[int, Query(ge=2000, le=2100)],
) -> HolidayListResponse:
    """그해 법정공휴일(특일 정보 API에서 받은 것)과 추가 휴일, 마지막 동기화 시각."""
    repo = TortoiseMentoringHolidayRepository()
    public = TortoisePublicHolidayRepository()
    start, end = date(year, 1, 1), date(year, 12, 31)
    custom = {h.holiday_date: h for h in await repo.list_between(start, end)}
    holidays = await BusinessCalendar(repo, public).holidays_between(start, end)
    sync = await public.get_sync(year)
    return HolidayListResponse(
        items=[
            HolidayResponse.custom(custom[h.day])
            if h.source is HolidaySource.CUSTOM
            else HolidayResponse(id=None, holiday_date=h.day, name=h.name, source=h.source)
            for h in holidays
        ],
        synced_at=sync.synced_at if sync else None,
    )


@router.post("/mentoring-holidays/sync", response_model=HolidaySyncResponse)
async def sync_public_holidays(_: AnyManager, service: SyncServiceDep) -> HolidaySyncResponse:
    """올해·내년 법정공휴일을 지금 받아 그해를 통째로 바꾼다. 실패하면 503 `holiday_sync_failed`."""
    results = await service.sync()
    return HolidaySyncResponse(
        years=[
            HolidaySyncYear(year=r.year, synced_at=r.synced_at, holiday_count=r.holiday_count)
            for r in results
        ]
    )


@router.post(
    "/mentoring-holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED
)
async def create_holiday(
    body: HolidayCreate, user: AnyManager, service: ServiceDep
) -> HolidayResponse:
    holiday = await service.create_holiday(body.holiday_date, body.name, actor_id=user.id)
    return HolidayResponse.custom(holiday)


@router.delete("/mentoring-holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(holiday_id: uuid.UUID, user: AnyManager, service: ServiceDep) -> Response:
    await service.delete_holiday(holiday_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CalendarHolidayResponse(BaseModel):
    holiday_date: date
    name: str
    source: HolidaySource


class CalendarHolidayListResponse(BaseModel):
    items: list[CalendarHolidayResponse]


@calendar_router.get("/holidays", response_model=CalendarHolidayListResponse)
async def list_calendar_holidays(
    _: CurrentUser,
    from_: Annotated[date, Query(alias="from")],
    to: date,
) -> CalendarHolidayListResponse:
    """기간 안 법정공휴일과 추가 휴일 (A107). 달력에 참고로 보여 줄 뿐 신청 가능 시간과는 무관하다.

    `to`는 포함, 기간은 100일까지(넘거나 거꾸로면 422 `invalid_holiday_range`).
    """
    if to < from_ or (to - from_).days >= CALENDAR_MAX_DAYS:
        raise BusinessRuleViolation(
            f"기간은 시작일부터 {CALENDAR_MAX_DAYS}일 안이어야 합니다.",
            code="invalid_holiday_range",
        )
    holidays = await BusinessCalendar(
        TortoiseMentoringHolidayRepository(), TortoisePublicHolidayRepository()
    ).holidays_between(from_, to)
    return CalendarHolidayListResponse(
        items=[
            CalendarHolidayResponse(holiday_date=h.day, name=h.name, source=h.source)
            for h in holidays
        ]
    )

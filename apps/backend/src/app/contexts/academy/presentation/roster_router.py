"""Airtable 수강생 명단 동기화 API (plan P5). 권한 roster.sync.

- 동기화 요청은 락을 잡고 실행 이력(RUNNING)을 만든 뒤 워커로 보내고 바로 202를 돌려준다.
  상태는 실행 이력 API로 확인한다. 같은 범위가 실행 중이면 409 roster_sync_in_progress.
- 전체 동기화·실패 목록은 전체 범위(SUPER_ADMIN), 과정·기수는 담당 범위(매니저·조교).
- 실행 이력은 자기 담당 범위의 실행만 보인다(최고 관리자는 전체).
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis

from app.contexts.academy.application.roster_queries import RosterQueries
from app.contexts.academy.application.roster_sync import RosterSyncDispatcher, RosterSyncService
from app.contexts.academy.domain.entities import RosterSyncRun, Student
from app.contexts.academy.domain.enums import (
    EnrollmentStatus,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
)
from app.contexts.academy.infrastructure.repositories import (
    TortoiseCohortRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.academy.presentation.roster_factory import build_roster_sync_service
from app.contexts.access.application.permissions import PermissionTarget
from app.contexts.access.presentation.dependencies import (
    PermissionCheckerDep,
    require_permission,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock
from app.core.redis import get_redis
from app.shared.errors import NotFoundError, ServiceUnavailableError

router = APIRouter(prefix="/admin", tags=["admin-rosters"])

READ = "academy.roster.read"
SYNC = "academy.roster.sync"


def get_roster_sync_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    redis: Annotated[Redis, Depends(get_redis)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RosterSyncService:
    if not settings.airtable_configured:
        raise ServiceUnavailableError(
            "Airtable 연동이 설정되지 않았습니다.", code="airtable_not_configured"
        )
    return build_roster_sync_service(
        settings,
        redis=redis,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        clock=clock,
    )


def get_roster_queries() -> RosterQueries:
    return RosterQueries(
        runs=TortoiseRosterSyncRunRepository(),
        students=TortoiseStudentRepository(),
        cohorts=TortoiseCohortRepository(),
    )


def get_dispatcher(request: Request) -> RosterSyncDispatcher:
    return cast("RosterSyncDispatcher", request.app.state.roster_sync_dispatcher)


SyncServiceDep = Annotated[RosterSyncService, Depends(get_roster_sync_service)]
QueriesDep = Annotated[RosterQueries, Depends(get_roster_queries)]
DispatcherDep = Annotated[RosterSyncDispatcher, Depends(get_dispatcher)]


# ---------------------------------------------------------------- 스키마
class RosterSyncRunResponse(BaseModel):
    id: uuid.UUID
    trigger: RosterSyncTrigger
    scope_type: RosterSyncScope
    bootcamp_id: uuid.UUID | None
    cohort_id: uuid.UUID | None
    status: RosterSyncStatus
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    upserted_count: int
    removed_count: int
    unmapped_count: int
    error_message: str | None

    @classmethod
    def of(cls, run: RosterSyncRun) -> "RosterSyncRunResponse":
        return cls(
            id=run.id,
            trigger=run.trigger,
            scope_type=run.scope_type,
            bootcamp_id=run.bootcamp_id,
            cohort_id=run.cohort_id,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            fetched_count=run.fetched_count,
            upserted_count=run.upserted_count,
            removed_count=run.removed_count,
            unmapped_count=run.unmapped_count,
            error_message=run.error_message,
        )


class RosterSyncRunPage(BaseModel):
    items: list[RosterSyncRunResponse]
    next_before: uuid.UUID | None  # 다음 페이지 커서 (없으면 끝)


class RosterStudentResponse(BaseModel):
    id: uuid.UUID
    airtable_record_id: str | None
    name: str
    phone_number: str | None
    email: str | None
    status: EnrollmentStatus
    hrd_net_status: StudentStatus
    user_id: uuid.UUID | None  # 가입한 회원 (없으면 미가입)
    is_removed_in_source: bool
    enrolled_at: date
    ended_at: date | None
    end_reason: str | None
    synced_at: datetime | None

    @classmethod
    def of(cls, s: Student) -> "RosterStudentResponse":
        return cls(
            id=s.id,
            airtable_record_id=s.airtable_record_id,
            name=s.name,
            phone_number=s.phone_number,
            email=s.email,
            status=s.status,
            hrd_net_status=s.hrd_net_status,
            user_id=s.user_id,
            is_removed_in_source=s.is_removed_in_source,
            enrolled_at=s.enrolled_at,
            ended_at=s.ended_at,
            end_reason=s.end_reason,
            synced_at=s.synced_at,
        )


class UnmappedRecordsResponse(BaseModel):
    run_id: uuid.UUID | None
    finished_at: datetime | None
    records: list[dict[str, Any]]


# ---------------------------------------------------------------- 동기화 요청
async def _start(
    service: RosterSyncService,
    dispatcher: RosterSyncDispatcher,
    user: User,
    scope_type: RosterSyncScope,
    **ids: uuid.UUID,
) -> RosterSyncRunResponse:
    run = await service.request(RosterSyncTrigger.MANUAL, scope_type, actor_id=user.id, **ids)
    try:
        await dispatcher.dispatch(run.id)
    except Exception as exc:
        await service.abort(run.id, reason="동기화 작업을 워커에 보내지 못했습니다.")
        raise ServiceUnavailableError(
            "동기화 작업을 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            code="roster_sync_dispatch_failed",
        ) from exc
    return RosterSyncRunResponse.of(run)


@router.post(
    "/rosters/sync", response_model=RosterSyncRunResponse, status_code=status.HTTP_202_ACCEPTED
)
async def sync_all_rosters(
    user: Annotated[User, Depends(require_permission(SYNC))],
    service: SyncServiceDep,
    dispatcher: DispatcherDep,
) -> RosterSyncRunResponse:
    """전체 동기화 (Airtable 기수 별칭이 설정된 모든 과정). 전체 범위 권한."""
    return await _start(service, dispatcher, user, RosterSyncScope.ALL)


@router.post(
    "/bootcamps/{bootcamp_id}/rosters/sync",
    response_model=RosterSyncRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_bootcamp_rosters(
    bootcamp_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(SYNC, bootcamp_param="bootcamp_id"))],
    service: SyncServiceDep,
    dispatcher: DispatcherDep,
) -> RosterSyncRunResponse:
    return await _start(
        service, dispatcher, user, RosterSyncScope.BOOTCAMP, bootcamp_id=bootcamp_id
    )


@router.post(
    "/cohorts/{cohort_id}/rosters/sync",
    response_model=RosterSyncRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_cohort_rosters(
    cohort_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(SYNC, cohort_param="cohort_id"))],
    service: SyncServiceDep,
    dispatcher: DispatcherDep,
) -> RosterSyncRunResponse:
    return await _start(service, dispatcher, user, RosterSyncScope.COHORT, cohort_id=cohort_id)


# ---------------------------------------------------------------- 조회
def _target(run: RosterSyncRun) -> PermissionTarget:
    if run.scope_type is RosterSyncScope.COHORT and run.cohort_id is not None:
        return PermissionTarget.cohort(run.cohort_id)
    if run.scope_type is RosterSyncScope.BOOTCAMP and run.bootcamp_id is not None:
        return PermissionTarget.bootcamp(run.bootcamp_id)
    return PermissionTarget.global_()


@router.get("/rosters/sync-runs", response_model=RosterSyncRunPage)
async def list_sync_runs(
    user: Annotated[User, Depends(require_permission(READ, any_scope=True))],
    queries: QueriesDep,
    checker: PermissionCheckerDep,
    before: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RosterSyncRunPage:
    """최근 실행부터. 담당 범위 밖의 실행은 빠지므로 한 페이지가 limit보다 적을 수 있다."""
    runs = await queries.recent_runs(before=before, limit=limit)
    visible = [r for r in runs if await checker.has(user.id, READ, _target(r))]
    return RosterSyncRunPage(
        items=[RosterSyncRunResponse.of(r) for r in visible],
        next_before=runs[-1].id if len(runs) == limit else None,
    )


@router.get("/rosters/sync-runs/{run_id}", response_model=RosterSyncRunResponse)
async def get_sync_run(
    run_id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(READ, any_scope=True))],
    queries: QueriesDep,
    checker: PermissionCheckerDep,
) -> RosterSyncRunResponse:
    run = await queries.get_run(run_id)
    if not await checker.has(user.id, READ, _target(run)):
        raise NotFoundError("동기화 실행을 찾을 수 없습니다.", code="roster_sync_run_not_found")
    return RosterSyncRunResponse.of(run)


@router.get("/cohorts/{cohort_id}/rosters", response_model=list[RosterStudentResponse])
async def list_cohort_rosters(
    cohort_id: uuid.UUID,
    _: Annotated[User, Depends(require_permission(READ, cohort_param="cohort_id"))],
    queries: QueriesDep,
    claimed: bool | None = None,
    include_removed: bool = False,
) -> list[RosterStudentResponse]:
    """기수 명단. claimed=true면 가입한 수강생만, false면 미가입만.

    원천(Airtable)에서 사라진 레코드는 기본으로 뺀다(include_removed=true면 포함).
    """
    students = await queries.cohort_students(
        cohort_id, claimed=claimed, include_removed=include_removed
    )
    return [RosterStudentResponse.of(s) for s in students]


@router.get("/rosters/unmapped", response_model=UnmappedRecordsResponse)
async def latest_unmapped_records(
    _: Annotated[User, Depends(require_permission(READ))],
    queries: QueriesDep,
) -> UnmappedRecordsResponse:
    """가장 최근에 성공한 전체 동기화에서 처리하지 못한 레코드 (운영진 확인 대상)."""
    run = await queries.latest_unmapped()
    if run is None:
        return UnmappedRecordsResponse(run_id=None, finished_at=None, records=[])
    return UnmappedRecordsResponse(
        run_id=run.id, finished_at=run.finished_at, records=run.unmapped_records
    )

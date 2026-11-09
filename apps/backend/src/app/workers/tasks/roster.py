"""Airtable 명단 동기화 작업 (얇은 래퍼, 로직은 academy RosterSyncService).

- `academy.roster_sync.execute(run_id)`: 수동 요청(API)이 만든 실행을 처리한다.
- `academy.roster_sync.scheduled`: 매시 정각 전체 동기화. Airtable 설정이 없으면 건너뛴다.

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from app.contexts.academy.application.roster_sync import RosterSyncService
from app.contexts.academy.domain.roster import RosterFieldMap
from app.contexts.academy.infrastructure.airtable_source import AirtableRosterSource
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.academy.infrastructure.roster_sync_lock import RedisRosterSyncLock
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.redis import create_redis
from app.core.uow import UnitOfWork
from app.integrations.airtable.client import AirtableClient
from app.workers.broker import broker

logger = logging.getLogger(__name__)

HOURLY = "0 * * * *"


def build_roster_sync_service(settings: Settings, redis: "Redis") -> RosterSyncService:
    clock = SystemClock()
    client = AirtableClient(
        token=settings.airtable_token.get_secret_value(), base_id=settings.airtable_base_id
    )
    return RosterSyncService(
        source=AirtableRosterSource(client, table=settings.airtable_table_id),
        field_map=RosterFieldMap(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
        students=TortoiseStudentRepository(),
        runs=TortoiseRosterSyncRunRepository(),
        lock=RedisRosterSyncLock(redis),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


@asynccontextmanager
async def _service() -> AsyncIterator[RosterSyncService]:
    settings = get_settings()
    redis = create_redis(settings.redis_url)
    try:
        yield build_roster_sync_service(settings, redis)
    finally:
        await redis.aclose()


@broker.task(task_name="academy.roster_sync.execute")
async def execute_roster_sync(run_id: str) -> None:
    async with _service() as service:
        run = await service.execute(uuid.UUID(run_id))
        logger.info("명단 동기화 %s: %s", run.id, run.status)


@broker.task(task_name="academy.roster_sync.scheduled", schedule=[{"cron": HOURLY}])
async def scheduled_roster_sync() -> None:
    if not get_settings().airtable_configured:
        logger.warning("Airtable 설정(AIRTABLE_*)이 없어 주기 명단 동기화를 건너뜁니다.")
        return
    async with _service() as service:
        run = await service.run_scheduled()
        if run is not None:
            logger.info("주기 명단 동기화 %s: %s", run.id, run.status)


class TaskiqRosterSyncDispatcher:
    """수동 동기화 실행을 워커로 보낸다 (API → taskiq). app.main이 app.state에 연결한다."""

    async def dispatch(self, run_id: uuid.UUID) -> None:
        await execute_roster_sync.kiq(str(run_id))

"""Airtable 명단 동기화 작업 (얇은 래퍼, 로직은 academy RosterSyncService).

- `academy.roster_sync.execute(run_id)`: 수동 요청(API)이 만든 실행을 처리한다.
- `academy.roster_sync.scheduled`: 매시 정각 전체 동기화. Airtable 설정이 없으면 건너뛴다.
동기화가 성공하면 멘토링 수강 종료 처리(`mentoring.enrollment_ended.process`)를
보낸다(decisions A39).

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.contexts.academy.application.roster_sync import RosterSyncService
from app.contexts.academy.domain.entities import RosterSyncRun
from app.contexts.academy.domain.enums import RosterSyncStatus
from app.contexts.academy.presentation.roster_factory import build_roster_sync_service
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.redis import create_redis
from app.workers.broker import broker
from app.workers.tasks.mentoring import process_enrollment_ended

logger = logging.getLogger(__name__)

HOURLY = "0 * * * *"


@asynccontextmanager
async def _service() -> AsyncIterator[RosterSyncService]:
    settings = get_settings()
    redis = create_redis(settings.redis_url)
    try:
        clock = SystemClock()
        yield build_roster_sync_service(
            settings,
            redis=redis,
            audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
            clock=clock,
        )
    finally:
        await redis.aclose()


@broker.task(task_name="academy.roster_sync.execute")
async def execute_roster_sync(run_id: str) -> None:
    async with _service() as service:
        run = await service.execute(uuid.UUID(run_id))
        logger.info("명단 동기화 %s: %s", run.id, run.status)
    await _after_sync(run)


@broker.task(task_name="academy.roster_sync.scheduled", schedule=[{"cron": HOURLY}])
async def scheduled_roster_sync() -> None:
    if not get_settings().airtable_configured:
        logger.warning("Airtable 설정(AIRTABLE_*)이 없어 주기 명단 동기화를 건너뜁니다.")
        return
    async with _service() as service:
        run = await service.run_scheduled()
        if run is not None:
            logger.info("주기 명단 동기화 %s: %s", run.id, run.status)
    if run is not None:
        await _after_sync(run)


async def _after_sync(run: RosterSyncRun) -> None:
    """동기화가 성공하면 수강 종료 처리를 워커로 보낸다 (명단 동기화와 따로 실패·재시도)."""
    if run.status is RosterSyncStatus.SUCCEEDED:
        await process_enrollment_ended.kiq()


class TaskiqRosterSyncDispatcher:
    """수동 동기화 실행을 워커로 보낸다 (API → taskiq). app.main이 app.state에 연결한다."""

    async def dispatch(self, run_id: uuid.UUID) -> None:
        await execute_roster_sync.kiq(str(run_id))

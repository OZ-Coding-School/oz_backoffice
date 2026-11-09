"""명단 동기화 서비스 조립 (API 라우터와 taskiq 작업이 함께 쓴다)."""

from redis.asyncio import Redis

from app.contexts.academy.application.cohort_master_sync import CohortMasterSync
from app.contexts.academy.application.roster_sync import RosterSyncService
from app.contexts.academy.domain.cohort_source import CohortFieldMap
from app.contexts.academy.domain.roster import RosterFieldMap
from app.contexts.academy.infrastructure.airtable_source import AirtableRosterSource
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.academy.infrastructure.roster_sync_lock import RedisRosterSyncLock
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.clock import Clock
from app.core.config import Settings
from app.core.uow import UnitOfWork
from app.integrations.airtable.client import AirtableClient


def build_roster_sync_service(
    settings: Settings, *, redis: "Redis", audit: AuditRecorder, clock: Clock
) -> RosterSyncService:
    client = AirtableClient(
        token=settings.airtable_token.get_secret_value(), base_id=settings.airtable_base_id
    )
    cohort_fields = CohortFieldMap()
    bootcamps = TortoiseBootcampRepository()
    cohorts = TortoiseCohortRepository()
    return RosterSyncService(
        source=AirtableRosterSource(client, table=settings.airtable_student_table_id),
        field_map=RosterFieldMap(),
        cohort_source=AirtableRosterSource(client, table=settings.airtable_bootcamp_table_id),
        master=CohortMasterSync(
            field_map=cohort_fields,
            hrd_bootcamps=TortoiseHrdNetBootcampRepository(),
            hrd_cohorts=TortoiseHrdNetBootcampCohortRepository(),
            bootcamps=bootcamps,
            cohorts=cohorts,
        ),
        cohort_field_map=cohort_fields,
        bootcamps=bootcamps,
        cohorts=cohorts,
        students=TortoiseStudentRepository(),
        runs=TortoiseRosterSyncRunRepository(),
        lock=RedisRosterSyncLock(redis),
        audit=audit,
        uow=UnitOfWork(),
        clock=clock,
    )

import pytest
from fakeredis import FakeAsyncRedis
from pydantic import SecretStr

from app.contexts.academy.presentation.roster_factory import build_roster_sync_service
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.clock import SystemClock
from app.core.config import Settings
from app.workers.tasks.roster import HOURLY, execute_roster_sync, scheduled_roster_sync
from tests.fakes.audit import InMemoryAuditLogRepository

pytestmark = pytest.mark.unit


def test_tasks_are_registered_with_schedule() -> None:
    assert execute_roster_sync.task_name == "academy.roster_sync.execute"
    assert scheduled_roster_sync.labels["schedule"] == [{"cron": HOURLY}]


def test_airtable_configured(settings: Settings) -> None:
    assert not settings.airtable_configured
    configured = settings.model_copy(
        update={
            "airtable_token": SecretStr("pat"),
            "airtable_base_id": "app",
            "airtable_student_table_id": "tblS",
            "airtable_bootcamp_table_id": "tblB",
        }
    )
    assert configured.airtable_configured


def test_service_composition(settings: Settings) -> None:
    clock = SystemClock()
    service = build_roster_sync_service(
        settings,
        redis=FakeAsyncRedis(),
        audit=AuditRecorder(InMemoryAuditLogRepository(), clock),
        clock=clock,
    )
    assert service is not None


async def test_scheduled_task_skips_without_airtable(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr("app.workers.tasks.roster.get_settings", lambda: settings)
    await scheduled_roster_sync.original_func()  # 설정이 없으면 아무것도 하지 않는다

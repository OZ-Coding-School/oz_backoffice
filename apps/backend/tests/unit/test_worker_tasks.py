import pytest
from fakeredis import FakeAsyncRedis
from pydantic import SecretStr

from app.core.config import Settings
from app.workers.tasks.roster import (
    HOURLY,
    airtable_configured,
    build_roster_sync_service,
    execute_roster_sync,
    scheduled_roster_sync,
)

pytestmark = pytest.mark.unit


def test_tasks_are_registered_with_schedule() -> None:
    assert execute_roster_sync.task_name == "academy.roster_sync.execute"
    assert scheduled_roster_sync.labels["schedule"] == [{"cron": HOURLY}]


def test_airtable_configured(settings: Settings) -> None:
    assert not airtable_configured(settings)
    configured = settings.model_copy(
        update={
            "airtable_token": SecretStr("pat"),
            "airtable_base_id": "app",
            "airtable_table_id": "tbl",
        }
    )
    assert airtable_configured(configured)


def test_service_composition(settings: Settings) -> None:
    assert build_roster_sync_service(settings, FakeAsyncRedis()) is not None


async def test_scheduled_task_skips_without_airtable(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr("app.workers.tasks.roster.get_settings", lambda: settings)
    await scheduled_roster_sync.original_func()  # 설정이 없으면 아무것도 하지 않는다

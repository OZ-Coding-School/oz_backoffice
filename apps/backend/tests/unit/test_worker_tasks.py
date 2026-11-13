import pytest
from fakeredis import FakeAsyncRedis
from pydantic import SecretStr

from app.contexts.academy.presentation.roster_factory import build_roster_sync_service
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.clock import SystemClock
from app.core.config import Settings
from app.workers.broker import broker
from app.workers.tasks import roster
from app.workers.tasks.contracts import DAILY_0005_KST, expire_contracts
from app.workers.tasks.mentoring import (
    build_assignment_service,
    build_enrollment_ended_service,
    build_meet_service,
    build_request_service,
    create_meet_space,
    create_space_with_retry,
    expire_assignments,
    expire_requests,
    process_enrollment_ended,
    sync_meet_spaces,
)
from app.workers.tasks.roster import HOURLY, execute_roster_sync, scheduled_roster_sync
from tests.fakes.audit import InMemoryAuditLogRepository

pytestmark = pytest.mark.unit


def test_tasks_are_registered_with_schedule() -> None:
    assert execute_roster_sync.task_name == "academy.roster_sync.execute"
    assert scheduled_roster_sync.labels["schedule"] == [{"cron": HOURLY}]


def test_contract_expiry_runs_daily_in_kst() -> None:
    assert expire_contracts.task_name == "educator.contracts.expire"
    assert expire_contracts.labels["schedule"] == [
        {"cron": "5 0 * * *", "cron_offset": "Asia/Seoul"}
    ]
    assert DAILY_0005_KST["cron_offset"] == "Asia/Seoul"


def test_assignment_expiry_runs_daily_at_midnight_kst() -> None:
    assert expire_assignments.task_name == "mentoring.assignments.expire"
    assert expire_assignments.labels["schedule"] == [
        {"cron": "0 0 * * *", "cron_offset": "Asia/Seoul"}
    ]
    assert build_assignment_service() is not None


def test_request_expiry_runs_every_10_minutes() -> None:
    assert expire_requests.task_name == "mentoring.requests.expire"
    assert expire_requests.labels["schedule"] == [{"cron": "*/10 * * * *"}]
    assert build_request_service() is not None


def test_broker_connection_has_no_read_timeout() -> None:
    """BRPOP 대기 중 읽기 타임아웃으로 워커가 죽지 않도록 socket_timeout을 끈다."""
    assert broker.connection_pool.connection_kwargs["socket_timeout"] is None


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


async def test_enrollment_ended_runs_after_successful_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """명단 동기화가 성공했을 때만 수강 종료 처리를 보낸다 (A39)."""
    from app.contexts.academy.domain.entities import RosterSyncRun
    from app.contexts.academy.domain.enums import RosterSyncStatus

    assert process_enrollment_ended.task_name == "mentoring.enrollment_ended.process"
    assert build_enrollment_ended_service() is not None
    sent: list[str] = []

    async def fake_kiq() -> None:
        sent.append("sent")

    monkeypatch.setattr(process_enrollment_ended, "kiq", fake_kiq)  # roster가 쓰는 같은 작업
    for status, expected in (
        (RosterSyncStatus.SUCCEEDED, 1),
        (RosterSyncStatus.FAILED, 1),
    ):
        run = RosterSyncRun.__new__(RosterSyncRun)
        run.status = status
        await roster._after_sync(run)
        assert len(sent) == expected


def test_meet_tasks_registered() -> None:
    assert create_meet_space.task_name == "mentoring.meet.create_space"
    assert sync_meet_spaces.task_name == "mentoring.meet.sync"
    assert sync_meet_spaces.labels["schedule"] == [{"cron": "*/10 * * * *"}]
    assert not build_meet_service().enabled  # 기본 MEET_DRIVER=disabled


async def test_create_space_retries_then_gives_up() -> None:
    import uuid

    from app.integrations.google.meet import MeetUnavailableError

    class Flaky:
        def __init__(self, failures: int) -> None:
            self.calls = 0
            self.failures = failures

        async def ensure_space(self, session_id: uuid.UUID) -> bool:
            self.calls += 1
            if self.calls <= self.failures:
                raise MeetUnavailableError()
            return True

    recovering = Flaky(failures=2)
    assert await create_space_with_retry(uuid.uuid4(), service=recovering, delays=(0, 0))  # type: ignore[arg-type]  # ensure_space만 쓴다
    assert recovering.calls == 3
    broken = Flaky(failures=5)
    assert not await create_space_with_retry(uuid.uuid4(), service=broken, delays=(0, 0))  # type: ignore[arg-type]
    assert broken.calls == 3  # 이후는 주기 작업(sync)이 다시 만든다


async def test_meet_event_tasks() -> None:
    from app.integrations.google.meet import MeetUnavailableError
    from app.integrations.google.meet_events import CONFERENCE_STARTED, MeetEvent
    from app.workers.tasks.mentoring import (
        handle_event_with_retry,
        handle_meet_event,
        subscribe_meet_events,
    )

    assert handle_meet_event.task_name == "mentoring.meet.events.handle"
    assert subscribe_meet_events.labels["schedule"] == [{"cron": "0 */6 * * *"}]
    event = MeetEvent("e1", CONFERENCE_STARTED, "conferenceRecords/c1")
    assert not await handle_event_with_retry(event)  # 기본 설정(disabled)이면 처리하지 않는다

    class Flaky:
        calls = 0

        async def handle(self, _: MeetEvent) -> bool:
            self.calls += 1
            if self.calls < 3:
                raise MeetUnavailableError()
            return True

    flaky = Flaky()
    assert await handle_event_with_retry(event, service=flaky, delays=(0, 0))  # type: ignore[arg-type]  # handle만 쓴다
    assert flaky.calls == 3
    await subscribe_meet_events.original_func()  # 설정이 없으면 아무것도 하지 않는다

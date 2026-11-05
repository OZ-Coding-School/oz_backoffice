from datetime import UTC, datetime

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.domain.entities import AuditLog
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


async def test_record_stores_log_with_clock_time() -> None:
    repo = InMemoryAuditLogRepository()
    recorder = AuditRecorder(repo, FixedClock(NOW))
    actor, target = new_id(), new_id()

    log = await recorder.record(
        actor_user_id=actor,
        action="identity.user.approve",
        target_type="user",
        target_id=target,
        before={"approval_status": "PENDING"},
        after={"approval_status": "APPROVED"},
    )

    assert repo.logs == [log]
    assert log.created_at == NOW
    assert log.actor_user_id == actor


async def test_list_for_target_is_newest_first_with_cursor() -> None:
    repo = InMemoryAuditLogRepository()
    recorder = AuditRecorder(repo, FixedClock(NOW))
    target = new_id()
    logs = [
        await recorder.record(
            actor_user_id=None, action=f"a.{i}", target_type="t", target_id=target
        )
        for i in range(3)
    ]

    first_page = await repo.list_for_target("t", target, limit=2)
    assert [log.action for log in first_page] == ["a.2", "a.1"]
    second_page = await repo.list_for_target("t", target, limit=2, before=first_page[-1].id)
    assert [log.action for log in second_page] == ["a.0"]
    assert logs[0] in second_page


@pytest.mark.parametrize(("action", "target_type"), [("", "t"), ("a", ""), ("a" * 101, "t")])
def test_invalid_audit_log_is_rejected(action: str, target_type: str) -> None:
    with pytest.raises(BusinessRuleViolation):
        AuditLog(action=action, target_type=target_type, target_id=None, created_at=NOW)

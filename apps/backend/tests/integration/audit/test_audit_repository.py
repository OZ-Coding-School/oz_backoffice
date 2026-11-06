from datetime import UTC, datetime

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import FixedClock
from app.core.uow import UnitOfWork
from app.shared.ids import new_id
from tests.factories.identity import make_user

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


async def test_record_and_list_with_cursor() -> None:
    users = TortoiseUserRepository()
    actor = make_user()
    await users.add(actor)
    repo = TortoiseAuditLogRepository()
    recorder = AuditRecorder(repo, FixedClock(NOW))
    target = new_id()

    for i in range(3):
        await recorder.record(
            actor_user_id=actor.id,
            action=f"test.action.{i}",
            target_type="sample",
            target_id=target,
            before={"step": i},
            after={"step": i + 1},
            ip="2001:db8::1",
        )

    page = await repo.list_for_target("sample", target, limit=2)
    assert [log.action for log in page] == ["test.action.2", "test.action.1"]
    assert page[0].after == {"step": 3}
    assert page[0].actor_user_id == actor.id
    rest = await repo.list_for_target("sample", target, limit=2, before=page[-1].id)
    assert [log.action for log in rest] == ["test.action.0"]


async def test_audit_log_rolls_back_with_unit_of_work() -> None:
    """업무 변경과 감사 로그가 같은 트랜잭션에 묶이는지 확인한다."""
    repo = TortoiseAuditLogRepository()
    recorder = AuditRecorder(repo, FixedClock(NOW))
    target = new_id()

    class Boom(Exception):
        pass

    async def fail() -> None:
        async with UnitOfWork():
            await recorder.record(
                actor_user_id=None, action="test.rollback", target_type="sample", target_id=target
            )
            raise Boom

    with pytest.raises(Boom):
        await fail()
    assert await repo.list_for_target("sample", target, limit=10) == []

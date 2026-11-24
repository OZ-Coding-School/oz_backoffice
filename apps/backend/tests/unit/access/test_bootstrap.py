from datetime import UTC, datetime

import pytest

from app.contexts.access.application.bootstrap import SuperAdminBootstrap
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.domain.enums import UserApprovalStatus
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation
from tests.factories.identity import make_user
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.identity import InMemoryUserRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


class Harness:
    def __init__(self) -> None:
        clock = FixedClock(NOW)
        self.users = InMemoryUserRepository()
        self.audit = InMemoryAuditLogRepository()
        self.bootstrap = SuperAdminBootstrap(
            users=UserAdministration(self.users, clock),
            audit=AuditRecorder(self.audit, clock),
            uow=FakeUnitOfWork(),
            staff_domain="nextrunners.co.kr",
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_creates_approved_user_and_grants_super_admin(h: Harness) -> None:
    result = await h.bootstrap.run(" Admin@NextRunners.co.kr ")

    assert result.user_created
    assert result.role_granted
    user = await h.users.get_by_email("admin@nextrunners.co.kr")
    assert user is not None
    assert (user.name, user.approval_status, user.approved_at, user.is_active) == (
        "admin",
        UserApprovalStatus.APPROVED,
        NOW,
        True,
    )
    assert user.is_super_admin  # 회원 필드 (A87)
    assert [log.action for log in h.audit.logs] == ["access.super_admin.enable"]


async def test_existing_pending_user_is_approved_and_rerun_is_noop(h: Harness) -> None:
    pending = make_user(email="kim@nextrunners.co.kr", name="김오즈")
    await h.users.add(pending)

    first = await h.bootstrap.run("kim@nextrunners.co.kr", name="무시됨")
    second = await h.bootstrap.run("kim@nextrunners.co.kr")

    assert (first.user.id, first.user.name, first.user_created) == (pending.id, "김오즈", False)
    assert first.user.is_approved
    assert (second.role_granted, second.user.is_super_admin, len(h.audit.logs)) == (False, True, 1)


@pytest.mark.parametrize("email", ["kim@gmail.com", "kim@nextrunners.co.kr.evil.com"])
async def test_rejects_non_staff_email(h: Harness, email: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.bootstrap.run(email)
    assert exc.value.code == "not_staff_email"
    assert h.audit.logs == []


async def test_rejects_suspended_user(h: Harness) -> None:
    user = make_user(email="kim@nextrunners.co.kr")
    user.approve(now=NOW)
    user.deactivate()
    await h.users.add(user)
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.bootstrap.run("kim@nextrunners.co.kr")
    assert exc.value.code == "account_disabled"

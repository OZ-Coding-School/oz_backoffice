"""내 정보 비밀번호 변경 (링크 인증, decisions A72)."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.password_change import PasswordChangeService
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.password_change import PasswordChangeState
from app.contexts.identity.infrastructure.login_attempts import RedisLoginAttempts
from app.contexts.identity.infrastructure.password_change_store import RedisPasswordChangeStore
from app.core.clock import FixedClock
from app.core.rate_limit import RedisRateLimiter
from app.integrations.notifications.mail import MailMessage
from app.shared.errors import BusinessRuleViolation, TooManyRequestsError
from tests.factories.identity import make_user
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.identity import InMemoryUserRepository
from tests.fakes.notifications import InMemoryMailSender
from tests.fakes.uow import FakeUnitOfWork
from tests.unit.identity.test_password_auth import FakeHasher

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)
EMAIL = "kim@gmail.com"


class FailingMail(InMemoryMailSender):
    async def send(self, message: MailMessage) -> None:
        raise RuntimeError("발송 실패")


class Harness:
    def __init__(self, redis: FakeAsyncRedis) -> None:
        self.clock = FixedClock(NOW)
        self.users = InMemoryUserRepository()
        self.mail = InMemoryMailSender()
        self.audit_logs = InMemoryAuditLogRepository()
        self.attempts = RedisLoginAttempts(redis)
        self.service = PasswordChangeService(
            users=self.users,
            store=RedisPasswordChangeStore(redis),
            limiter=RedisRateLimiter(redis),
            hasher=FakeHasher(),
            attempts=self.attempts,
            mail=self.mail,
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
            sender_name="오즈코딩스쿨",
            frontend_base_url="http://front.test/",
        )

    async def member(self, **overrides: object) -> User:
        values: dict[str, object] = {"email": EMAIL, "hashed_password": "h:abcd123!", **overrides}
        user = make_user(**values)
        await self.users.add(user)
        return user

    def later(self, **delta: float) -> None:
        self.clock.set(self.clock.now() + timedelta(**delta))

    def token(self) -> str:
        match = re.search(r"/password-change/verify\?token=(\S+)", self.mail.sent[-1].text)
        assert match
        return unquote(match.group(1))


@pytest.fixture
def h(fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(fake_redis)


async def test_link_verify_change_flow(h: Harness) -> None:
    user = await h.member()
    status = await h.service.status(user.id)
    assert (status.available, status.state) == (True, PasswordChangeState.NONE)

    sent = await h.service.send_link(user.id)
    assert (sent.state, sent.expires_at) == (PasswordChangeState.SENT, NOW + timedelta(minutes=30))
    assert h.mail.sent[-1].to == EMAIL
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.change(user.id, "newpass1!")  # 아직 링크를 누르지 않았다
    assert exc.value.code == "password_change_not_verified"

    h.later(minutes=29)
    await h.service.verify(h.token())
    status = await h.service.status(user.id)
    assert (status.state, status.expires_at) == (
        PasswordChangeState.VERIFIED,
        NOW + timedelta(minutes=39),
    )
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.verify(h.token())  # 한 번만 쓴다
    assert exc.value.code == "password_link_invalid"

    await h.attempts.record_failure(EMAIL)
    await h.service.change(user.id, "newpass1!")
    saved = await h.users.get(user.id)
    assert saved is not None
    assert saved.hashed_password == "h:newpass1!"
    assert [log.action for log in h.audit_logs.logs] == ["identity.password.change"]
    assert (await h.service.status(user.id)).state is PasswordChangeState.NONE
    assert await h.attempts.locked_for(EMAIL) == 0


async def test_link_expires_after_thirty_minutes_and_change_window_is_ten(h: Harness) -> None:
    user = await h.member()
    await h.service.send_link(user.id)
    token = h.token()
    h.later(minutes=30)
    assert (await h.service.status(user.id)).state is PasswordChangeState.NONE
    with pytest.raises(BusinessRuleViolation):
        await h.service.verify(token)

    h.later(minutes=1)
    await h.service.send_link(user.id)
    await h.service.verify(h.token())
    h.later(minutes=10)
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.change(user.id, "newpass1!")
    assert exc.value.code == "password_change_not_verified"


async def test_new_link_invalidates_previous_and_resend_rules(h: Harness) -> None:
    user = await h.member()
    await h.service.send_link(user.id)
    first = h.token()
    with pytest.raises(TooManyRequestsError) as exc:
        await h.service.send_link(user.id)  # 1분 간격
    assert exc.value.code == "resend_too_soon"
    h.later(seconds=60)
    await h.service.send_link(user.id)
    with pytest.raises(BusinessRuleViolation):
        await h.service.verify(first)  # 전 링크는 무효
    for _ in range(3):
        h.later(seconds=60)
        await h.service.send_link(user.id)
    h.later(seconds=60)
    with pytest.raises(TooManyRequestsError) as exc:
        await h.service.send_link(user.id)  # 하루 5회
    assert exc.value.code == "rate_limited"


async def test_google_only_account_is_not_available(h: Harness) -> None:
    user = await h.member(hashed_password=None)
    assert (await h.service.status(user.id)).available is False
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.send_link(user.id)
    assert exc.value.code == "password_not_available"


async def test_password_rules_apply_and_failed_mail_leaves_no_link(h: Harness) -> None:
    user = await h.member()
    await h.service.send_link(user.id)
    await h.service.verify(h.token())
    with pytest.raises(BusinessRuleViolation):
        await h.service.change(user.id, "short")
    assert (await h.service.status(user.id)).state is PasswordChangeState.VERIFIED

    other = make_user(email="lee@gmail.com", hashed_password="h:abcd123!")
    await h.users.add(other)
    h.service._mail = FailingMail()
    with pytest.raises(RuntimeError):
        await h.service.send_link(other.id)
    assert (await h.service.status(other.id)).state is PasswordChangeState.NONE


async def test_unknown_token_is_invalid(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.verify("nope")
    assert exc.value.code == "password_link_invalid"

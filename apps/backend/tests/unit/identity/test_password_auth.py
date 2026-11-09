import re
from datetime import UTC, datetime

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.password_auth import (
    PasswordLoginService,
    PasswordResetService,
)
from app.contexts.identity.application.tokens import TokenService
from app.contexts.identity.application.verification_codes import VerificationCodes
from app.contexts.identity.infrastructure.login_attempts import (
    LOCK_SECONDS,
    RedisLoginAttempts,
)
from app.contexts.identity.infrastructure.token_store import RedisRefreshTokenStore
from app.contexts.identity.infrastructure.verification_store import RedisChallengeStore
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.rate_limit import RedisRateLimiter
from app.core.security import JWTService
from app.shared.errors import AuthenticationError, BusinessRuleViolation, TooManyRequestsError
from tests.factories.identity import make_user
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.identity import InMemoryUserRepository
from tests.fakes.notifications import InMemoryMailSender
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime.now(UTC)  # 토큰 만료를 실제 시각으로 검사하므로 현재 시각으로 고정
EMAIL = "kim@gmail.com"


class FakeHasher:
    def __init__(self) -> None:
        self.outdated: set[str] = set()

    async def hash(self, password: str) -> str:
        return f"h:{password}"

    async def verify(self, hashed: str, password: str) -> bool:
        return hashed == f"h:{password}"

    def needs_rehash(self, hashed: str) -> bool:
        return hashed in self.outdated


class Harness:
    def __init__(self, settings: Settings, redis: FakeAsyncRedis) -> None:
        self.clock = FixedClock(NOW)
        self.users = InMemoryUserRepository()
        self.hasher = FakeHasher()
        self.attempts = RedisLoginAttempts(redis)
        self.mail = InMemoryMailSender()
        self.audit_logs = InMemoryAuditLogRepository()
        tokens = TokenService(
            JWTService(settings), RedisRefreshTokenStore(redis, ttl_seconds=600), self.clock
        )
        self.tokens = tokens
        self.login = PasswordLoginService(
            users=self.users,
            hasher=self.hasher,
            attempts=self.attempts,
            tokens=tokens,
            uow=FakeUnitOfWork(),
            clock=self.clock,
            dummy_hash="h:dummy-unknown",
        )
        self.reset = PasswordResetService(
            users=self.users,
            codes=VerificationCodes(
                challenges=RedisChallengeStore(redis),
                limiter=RedisRateLimiter(redis),
                clock=self.clock,
                secret="secret",
            ),
            hasher=self.hasher,
            attempts=self.attempts,
            mail=self.mail,
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            sender_name="오즈코딩스쿨",
        )

    async def member(self, **overrides: object) -> None:
        await self.users.add(make_user(email=EMAIL, hashed_password="h:abcd123!", **overrides))


@pytest.fixture
def h(settings: Settings, fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(settings, fake_redis)


async def test_login_issues_tokens_and_records_login(h: Harness) -> None:
    await h.member()
    result = await h.login.login(" Kim@Gmail.com ", "abcd123!")

    assert h.tokens.read_access(result.tokens.access_token) == result.user.id
    assert result.user.last_login_at == NOW


@pytest.mark.parametrize("email", [EMAIL, "nobody@gmail.com", "not-email"])
async def test_wrong_credentials_are_indistinguishable(h: Harness, email: str) -> None:
    await h.member()
    with pytest.raises(AuthenticationError) as exc:
        await h.login.login(email, "wrong123!")
    assert exc.value.code == "invalid_credentials"


async def test_google_only_account_cannot_use_password(h: Harness) -> None:
    await h.users.add(make_user(email="staff@nextrunners.co.kr"))
    with pytest.raises(AuthenticationError) as exc:
        await h.login.login("staff@nextrunners.co.kr", "abcd123!")
    assert exc.value.code == "invalid_credentials"


@pytest.mark.parametrize("registered", [True, False])
async def test_five_failures_lock_for_fifteen_minutes(h: Harness, registered: bool) -> None:
    if registered:
        await h.member()
    for _ in range(4):
        with pytest.raises(AuthenticationError):
            await h.login.login(EMAIL, "wrong123!")
    with pytest.raises(TooManyRequestsError) as fifth:
        await h.login.login(EMAIL, "wrong123!")
    assert (fifth.value.code, fifth.value.retry_after) == ("login_locked", LOCK_SECONDS)
    with pytest.raises(TooManyRequestsError):  # 잠긴 동안에는 맞는 비밀번호도 거부
        await h.login.login(EMAIL, "abcd123!")


async def test_success_clears_failures(h: Harness) -> None:
    await h.member()
    for _ in range(4):
        with pytest.raises(AuthenticationError):
            await h.login.login(EMAIL, "wrong123!")
    await h.login.login(EMAIL, "abcd123!")
    for _ in range(4):  # 다시 4번까지는 잠기지 않는다
        with pytest.raises(AuthenticationError):
            await h.login.login(EMAIL, "wrong123!")


async def test_pending_member_can_login_but_suspended_cannot(h: Harness) -> None:
    await h.member()  # 승인 대기 (A6)
    assert (await h.login.login(EMAIL, "abcd123!")).user.email == EMAIL

    suspended = make_user(email="lee@gmail.com", hashed_password="h:abcd123!")
    suspended.approve(now=NOW)
    suspended.deactivate()
    await h.users.add(suspended)
    with pytest.raises(AuthenticationError) as exc:
        await h.login.login("lee@gmail.com", "abcd123!")
    assert exc.value.code == "account_disabled"


async def test_outdated_hash_is_rehashed_on_login(h: Harness) -> None:
    await h.member()
    h.hasher.outdated.add("h:abcd123!")
    h.hasher.hash = lambda password: _async(f"h:{password}")  # type: ignore[method-assign]
    result = await h.login.login(EMAIL, "abcd123!")
    assert result.user.hashed_password == "h:abcd123!"


async def _async(value: str) -> str:
    return value


def _code(text: str) -> str:
    match = re.search(r"\b(\d{6})\b", text)
    assert match
    return match.group(1)


async def test_reset_flow_unlocks_login(h: Harness) -> None:
    await h.member()
    for _ in range(5):
        with pytest.raises((AuthenticationError, TooManyRequestsError)):
            await h.login.login(EMAIL, "wrong123!")

    await h.reset.request_code(EMAIL, client_ip="1.2.3.4")
    assert h.mail.sent[0].subject.startswith("[오즈코딩스쿨] 비밀번호 재설정 인증코드 ")
    await h.reset.reset(EMAIL, _code(h.mail.sent[0].text), "newpass1!")

    result = await h.login.login(EMAIL, "newpass1!")  # 잠금이 풀린다 (A32)
    assert result.user.hashed_password == "h:newpass1!"
    assert h.audit_logs.logs[-1].action == "identity.password.reset"


async def test_reset_code_for_unknown_email_is_silent(h: Harness) -> None:
    await h.users.add(make_user(email="staff@nextrunners.co.kr"))  # Google 전용
    for email in ("nobody@gmail.com", "staff@nextrunners.co.kr"):
        await h.reset.request_code(email, client_ip="1.2.3.4")  # 오류 없이 끝난다
        with pytest.raises(TooManyRequestsError):  # 재발송 간격도 가입자와 같게 동작
            await h.reset.request_code(email, client_ip="1.2.3.4")
        with pytest.raises(BusinessRuleViolation) as exc:
            await h.reset.reset(email, "123456", "newpass1!")
        assert exc.value.code == "invalid_verification_code"
    assert h.mail.sent == []


async def test_reset_validates_new_password_first(h: Harness) -> None:
    await h.member()
    await h.reset.request_code(EMAIL, client_ip="1.2.3.4")
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.reset.reset(EMAIL, _code(h.mail.sent[0].text), "weak")
    assert exc.value.code == "invalid_password"
    # 비밀번호가 규칙에 맞지 않으면 코드를 소모하지 않는다
    await h.reset.reset(EMAIL, _code(h.mail.sent[0].text), "newpass1!")

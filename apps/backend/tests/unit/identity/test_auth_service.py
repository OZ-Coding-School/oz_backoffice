from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.identity.application.auth_service import (
    SessionService,
    StaffGoogleLoginService,
    UserQueries,
)
from app.contexts.identity.application.tokens import TokenService
from app.contexts.identity.domain.enums import SocialLoginProvider, UserApprovalStatus
from app.contexts.identity.infrastructure.token_store import (
    RedisOAuthStateStore,
    RedisRefreshTokenStore,
)
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.security import JWTService
from app.integrations.google.oauth import GoogleIdentity
from app.shared.errors import AuthenticationError
from tests.factories.identity import make_user
from tests.fakes.identity import FakeGoogleAuthenticator, InMemoryUserRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

STAFF = GoogleIdentity(
    subject="google-sub-1", email="kim@nextrunners.co.kr", name="김오즈", hosted_domain="x"
)


class Harness:
    def __init__(self, settings: Settings, redis: FakeAsyncRedis) -> None:
        self.clock = FixedClock(datetime.now(UTC))
        self.users = InMemoryUserRepository()
        self.google = FakeGoogleAuthenticator()
        self.google.identities["good-code"] = STAFF
        store = RedisRefreshTokenStore(redis, ttl_seconds=settings.refresh_token_ttl_seconds)
        self.tokens = TokenService(JWTService(settings), store, self.clock)
        self.uow = FakeUnitOfWork()
        self.login = StaffGoogleLoginService(
            google=self.google,
            states=RedisOAuthStateStore(redis),
            users=self.users,
            tokens=self.tokens,
            uow=self.uow,
            clock=self.clock,
        )
        self.sessions = SessionService(users=self.users, tokens=self.tokens)
        self.queries = UserQueries(self.users)

    async def state(self) -> str:
        url = await self.login.start()
        return parse_qs(urlparse(url).query)["state"][0]


@pytest.fixture
def h(settings: Settings, fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(settings, fake_redis)


async def test_first_login_creates_pending_staff_user(h: Harness) -> None:
    result = await h.login.complete(code="good-code", state=await h.state())

    user = result.user
    assert (user.email, user.name) == ("kim@nextrunners.co.kr", "김오즈")
    assert user.approval_status is UserApprovalStatus.PENDING
    assert user.email_verified_at == h.clock.now()
    assert user.last_login_at == h.clock.now()
    assert h.tokens.read_access(result.tokens.access_token) == user.id
    # PKCE verifier가 code 교환에 전달된다
    assert h.google.exchanged[0][0] == "good-code"
    assert len(h.google.exchanged[0][1]) >= 43


async def test_second_login_reuses_linked_account(h: Harness) -> None:
    first = await h.login.complete(code="good-code", state=await h.state())
    second = await h.login.complete(code="good-code", state=await h.state())
    assert second.user.id == first.user.id
    assert len(h.users.users) == 1
    assert len(h.users.oauth_accounts) == 1


async def test_login_links_existing_user_with_same_email(h: Harness) -> None:
    existing = make_user(email="kim@nextrunners.co.kr")
    await h.users.add(existing)

    result = await h.login.complete(code="good-code", state=await h.state())

    assert result.user.id == existing.id
    linked = await h.users.get_by_oauth(SocialLoginProvider.GOOGLE, "google-sub-1")
    assert linked is not None
    assert linked.id == existing.id


async def test_state_is_single_use_and_must_exist(h: Harness) -> None:
    state = await h.state()
    await h.login.complete(code="good-code", state=state)
    for bad_state in (state, "unknown"):
        with pytest.raises(AuthenticationError) as exc:
            await h.login.complete(code="good-code", state=bad_state)
        assert exc.value.code == "oauth_state_invalid"


async def test_google_failure_is_propagated(h: Harness) -> None:
    with pytest.raises(AuthenticationError) as exc:
        await h.login.complete(code="bad-code", state=await h.state())
    assert exc.value.code == "google_auth_failed"
    assert h.users.users == {}


async def test_suspended_user_cannot_login(h: Harness) -> None:
    user = make_user(email="kim@nextrunners.co.kr")
    user.approve(now=h.clock.now())
    user.deactivate()
    await h.users.add(user)

    with pytest.raises(AuthenticationError) as exc:
        await h.login.complete(code="good-code", state=await h.state())
    assert exc.value.code == "account_disabled"
    assert h.uow.rollbacks == 1


async def test_refresh_rotates_and_blocks_suspended_user(h: Harness) -> None:
    login = await h.login.complete(code="good-code", state=await h.state())
    renewed = await h.sessions.refresh(login.tokens.refresh_token)
    assert h.tokens.read_access(renewed.access_token) == login.user.id

    user = await h.users.get(login.user.id)
    assert user is not None
    user.approve(now=h.clock.now())
    user.deactivate()
    await h.users.save(user)
    with pytest.raises(AuthenticationError) as exc:
        await h.sessions.refresh(renewed.refresh_token)
    assert exc.value.code == "account_disabled"


async def test_logout_revokes_refresh(h: Harness) -> None:
    login = await h.login.complete(code="good-code", state=await h.state())
    await h.sessions.logout(login.tokens.refresh_token)
    with pytest.raises(AuthenticationError):
        await h.sessions.refresh(login.tokens.refresh_token)


async def test_get_authenticated_user(h: Harness) -> None:
    login = await h.login.complete(code="good-code", state=await h.state())
    assert (await h.queries.get_authenticated(login.user.id)).id == login.user.id

    with pytest.raises(AuthenticationError) as exc:
        await h.queries.get_authenticated(make_user().id)
    assert exc.value.code == "token_invalid"

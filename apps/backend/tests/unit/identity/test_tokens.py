from datetime import UTC, datetime, timedelta

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.identity.application.tokens import ConsumedRefresh, TokenService
from app.contexts.identity.infrastructure.token_store import (
    RedisOAuthStateStore,
    RedisRefreshTokenStore,
)
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.errors import AuthenticationError
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime.now(UTC))


@pytest.fixture
def tokens(settings: Settings, fake_redis: FakeAsyncRedis, clock: FixedClock) -> TokenService:
    store = RedisRefreshTokenStore(fake_redis, ttl_seconds=settings.refresh_token_ttl_seconds)
    return TokenService(JWTService(settings), store, clock, reuse_grace_seconds=GRACE)


GRACE = 10


def later(clock: FixedClock, seconds: float) -> None:
    clock.set(clock.now() + timedelta(seconds=seconds))


async def test_issue_and_read_access(tokens: TokenService) -> None:
    user_id = new_id()
    issued = await tokens.issue(user_id)
    assert tokens.read_access(issued.access_token) == user_id
    with pytest.raises(AuthenticationError) as exc:
        tokens.read_access(issued.refresh_token)  # refresh는 access로 쓸 수 없다
    assert exc.value.code == "token_invalid"


async def test_refresh_rotates_once(tokens: TokenService) -> None:
    user_id = new_id()
    issued = await tokens.issue(user_id)

    assert await tokens.consume_refresh(issued.refresh_token) == ConsumedRefresh(user_id, True)
    renewed = await tokens.issue(user_id)
    assert await tokens.consume_refresh(renewed.refresh_token) == ConsumedRefresh(user_id, True)


async def test_reused_refresh_revokes_all_sessions(tokens: TokenService, clock: FixedClock) -> None:
    user_id = new_id()
    stolen = await tokens.issue(user_id)
    other_device = await tokens.issue(user_id)
    await tokens.consume_refresh(stolen.refresh_token)
    later(clock, GRACE + 0.001)  # 유예 시간이 지난 재사용은 탈취로 본다

    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(stolen.refresh_token)
    assert exc.value.code == "refresh_token_reused"
    # 같은 사용자의 다른 세션도 폐기된다
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(other_device.refresh_token)
    assert exc.value.code == "refresh_token_revoked"


async def test_revoked_refresh_cannot_be_used(tokens: TokenService) -> None:
    issued = await tokens.issue(new_id())
    await tokens.revoke(issued.refresh_token)
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_reused"


async def test_revoke_ignores_invalid_token(tokens: TokenService) -> None:
    await tokens.revoke("not-a-jwt")


async def test_expired_refresh_is_rejected(tokens: TokenService, clock: FixedClock) -> None:
    clock.set(datetime.now(UTC) - timedelta(days=30))
    issued = await tokens.issue(new_id())
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "token_expired"


async def test_unknown_refresh_is_rejected(
    tokens: TokenService, fake_redis: FakeAsyncRedis
) -> None:
    issued = await tokens.issue(new_id())
    await fake_redis.flushall()  # Redis에서 사라진 토큰 (만료·초기화)
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_revoked"


async def test_reuse_within_grace_gives_access_only(
    tokens: TokenService, clock: FixedClock
) -> None:
    """여러 탭이 같은 refresh로 동시에 갱신하면 늦게 온 쪽은 access만 받는다 (A60)."""
    user_id = new_id()
    issued = await tokens.issue(user_id)
    await tokens.consume_refresh(issued.refresh_token)
    renewed = await tokens.issue(user_id)

    later(clock, GRACE)  # 경계: 정확히 유예 시간까지는 허용
    assert await tokens.consume_refresh(issued.refresh_token) == ConsumedRefresh(user_id, False)
    # 유예로 다시 쓴 것은 다른 세션을 건드리지 않는다
    assert await tokens.consume_refresh(renewed.refresh_token) == ConsumedRefresh(user_id, True)


async def test_logout_ends_reuse_grace(tokens: TokenService) -> None:
    user_id = new_id()
    issued = await tokens.issue(user_id)
    await tokens.consume_refresh(issued.refresh_token)
    renewed = await tokens.issue(user_id)
    await tokens.revoke(renewed.refresh_token)  # 로그아웃

    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_reused"


async def test_revoke_all_ends_reuse_grace(tokens: TokenService, clock: FixedClock) -> None:
    user_id = new_id()
    issued = await tokens.issue(user_id)
    await tokens.consume_refresh(issued.refresh_token)
    later(clock, 1)
    await tokens.revoke_all(user_id)  # 계정 정지·탈취 탐지

    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_reused"


async def test_logged_out_refresh_has_no_grace(tokens: TokenService) -> None:
    issued = await tokens.issue(new_id())
    await tokens.revoke(issued.refresh_token)
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_reused"


async def test_used_record_without_timestamp_has_no_grace(
    tokens: TokenService, fake_redis: FakeAsyncRedis
) -> None:
    """사용 시각을 기록하기 전(A60 이전)에 쓰인 토큰은 유예 없이 재사용으로 본다."""
    user_id = new_id()
    issued = await tokens.issue(user_id)
    await tokens.consume_refresh(issued.refresh_token)
    keys = [k async for k in fake_redis.scan_iter("oz:identity:refresh-used:*")]
    await fake_redis.set(keys[0], str(user_id))
    with pytest.raises(AuthenticationError) as exc:
        await tokens.consume_refresh(issued.refresh_token)
    assert exc.value.code == "refresh_token_reused"


async def test_oauth_state_is_single_use(fake_redis: FakeAsyncRedis) -> None:
    states = RedisOAuthStateStore(fake_redis)
    await states.save("state-1", "verifier")
    assert await states.pop("state-1") == "verifier"
    assert await states.pop("state-1") is None

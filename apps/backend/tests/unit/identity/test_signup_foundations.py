from datetime import UTC, datetime, timedelta

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.identity.domain.credentials import validate_password
from app.contexts.identity.domain.verification import (
    ChallengeKind,
    CodeChallenge,
    SignupSession,
)
from app.contexts.identity.infrastructure.passwords import Argon2PasswordHasher
from app.contexts.identity.infrastructure.verification_store import (
    RedisChallengeStore,
    RedisSignupSessionStore,
)
from app.core.client_ip import resolve_client_ip
from app.core.rate_limit import RedisRateLimiter
from app.shared.errors import BusinessRuleViolation

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, tzinfo=UTC)


@pytest.mark.parametrize("password", ["abcd123!", "A1!" + "x" * 61, "한글도OK123!"])
def test_valid_passwords(password: str) -> None:
    validate_password(password)


@pytest.mark.parametrize(
    "password",
    ["abc12!", "A1!" + "x" * 62, "abcdefg1", "abcdefg!", "1234567!", "가나다라마바1!"],
)
def test_invalid_passwords(password: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        validate_password(password)
    assert exc.value.code == "invalid_password"


@pytest.mark.parametrize(
    ("peer", "forwarded", "trusted", "expected"),
    [
        ("1.2.3.4", None, [], "1.2.3.4"),
        ("1.2.3.4", "9.9.9.9", [], "1.2.3.4"),  # 신뢰 프록시가 없으면 헤더 무시
        ("10.0.0.5", "9.9.9.9", ["10.0.0.0/8"], "9.9.9.9"),
        ("10.0.0.5", "6.6.6.6, 9.9.9.9", ["10.0.0.0/8"], "9.9.9.9"),  # 위조 앞부분 무시
        ("10.0.0.5", "9.9.9.9, 10.0.0.7", ["10.0.0.0/8"], "9.9.9.9"),  # 프록시 체인
        ("8.8.8.8", "9.9.9.9", ["10.0.0.0/8"], "8.8.8.8"),  # 신뢰하지 않는 연결
        (None, None, [], "unknown"),
    ],
)
def test_resolve_client_ip(
    peer: str | None, forwarded: str | None, trusted: list[str], expected: str
) -> None:
    assert resolve_client_ip(peer, forwarded, trusted) == expected


async def test_rate_limiter_fixed_window(fake_redis: FakeAsyncRedis) -> None:
    limiter = RedisRateLimiter(fake_redis)
    results = [
        await limiter.hit("mail", "kim@gmail.com", limit=2, window_seconds=3600) for _ in range(3)
    ]
    assert [r.allowed for r in results] == [True, True, False]
    assert 3590 <= results[2].retry_after <= 3600
    other = await limiter.hit("mail", "lee@gmail.com", limit=2, window_seconds=3600)
    assert other.allowed


async def test_challenge_and_session_stores(fake_redis: FakeAsyncRedis) -> None:
    challenges = RedisChallengeStore(fake_redis)
    challenge = CodeChallenge(
        target="kim@gmail.com", code_hash="h", sent_at=NOW, expires_at=NOW + timedelta(minutes=10)
    )
    await challenges.put(ChallengeKind.SIGNUP_EMAIL, "kim@gmail.com", challenge, ttl_seconds=600)
    assert await challenges.get(ChallengeKind.SIGNUP_EMAIL, "kim@gmail.com") == challenge
    assert await challenges.get(ChallengeKind.SIGNUP_PHONE, "kim@gmail.com") is None
    keys = [k.decode() if isinstance(k, bytes) else k for k in await fake_redis.keys("*")]
    assert not any("kim@gmail.com" in k for k in keys)  # 키에 개인정보를 넣지 않는다
    await challenges.delete(ChallengeKind.SIGNUP_EMAIL, "kim@gmail.com")
    assert await challenges.get(ChallengeKind.SIGNUP_EMAIL, "kim@gmail.com") is None

    sessions = RedisSignupSessionStore(fake_redis)
    session = SignupSession(
        email="kim@gmail.com",
        email_verified_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
        phone_number="01012345678",
        phone_verified_at=NOW,
    )
    await sessions.put("token", session, ttl_seconds=1800)
    assert await sessions.get("token") == session
    assert session.is_complete


async def test_argon2_hasher() -> None:
    hasher = Argon2PasswordHasher()
    hashed = await hasher.hash("abcd123!")
    assert hashed.startswith("$argon2id$")
    assert await hasher.verify(hashed, "abcd123!")
    assert not await hasher.verify(hashed, "wrong123!")
    assert not await hasher.verify("not-a-hash", "abcd123!")
    assert not hasher.needs_rehash(hashed)

"""Redis 기반 refresh 토큰·OAuth state 저장소.

키:
- `oz:identity:refresh:<jti>` → user_id (활성 refresh, TTL = refresh 수명)
- `oz:identity:refresh-used:<jti>` → `user_id|사용 시각(ISO 8601)|R(회전) 또는 V(폐기)`
  (회전·폐기된 refresh, 재사용 탐지·유예 판정용, TTL = refresh 수명)
- `oz:identity:refresh-user:<user_id>` → jti 집합 (전체 폐기용)
- `oz:identity:refresh-revoked-at:<user_id>` → 마지막 로그아웃·전체 폐기 시각(ISO 8601)
  (그 전에 회전된 토큰은 유예하지 않는다, TTL = refresh 수명)
- `oz:identity:oauth-state:<state>` → PKCE verifier (TTL 10분, 한 번만 사용)
"""

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.contexts.identity.domain.sessions import RefreshLookup

_PREFIX = "oz:identity"


def _text(value: bytes | str | None) -> str | None:
    """decode_responses=True 클라이언트는 str을 돌려주지만 타입은 bytes | str로 선언돼 있다."""
    return value.decode() if isinstance(value, bytes) else value


def _active(jti: str) -> str:
    return f"{_PREFIX}:refresh:{jti}"


def _used(jti: str) -> str:
    return f"{_PREFIX}:refresh-used:{jti}"


def _user(user_id: uuid.UUID | str) -> str:
    return f"{_PREFIX}:refresh-user:{user_id}"


def _revoked_at(user_id: uuid.UUID | str) -> str:
    return f"{_PREFIX}:refresh-revoked-at:{user_id}"


def _stamp(moment: datetime) -> str:
    """시각을 잃는 값 없이 문자열로 (ISO 8601, UTC)."""
    return moment.astimezone(UTC).isoformat()


def _from_stamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


class RedisRefreshTokenStore:
    def __init__(self, redis: "Redis", *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def save(self, jti: str, user_id: uuid.UUID) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_active(jti), str(user_id), ex=self._ttl)
            pipe.sadd(_user(user_id), jti)
            pipe.expire(_user(user_id), self._ttl)
            await pipe.execute()

    async def consume(self, jti: str, *, now: datetime) -> RefreshLookup | None:
        # GETDEL은 원자적이다. 같은 토큰으로 동시에 갱신하면 하나만 회전되고
        # 나머지는 재사용으로 돌아간다 (유예 판정은 TokenService, decisions A60)
        user_id = _text(await self._redis.getdel(_active(jti)))
        if user_id is not None:
            await self._mark_used(jti, user_id, now=now, rotated=True)
            return RefreshLookup(user_id=uuid.UUID(user_id), reused=False)
        used = _text(await self._redis.get(_used(jti)))
        if used is None:
            return None
        if "|" not in used:
            # 사용 시각을 기록하기 전(A60 이전)에 쓰인 토큰: 유예 없이 재사용으로 본다
            return RefreshLookup(user_id=uuid.UUID(used), reused=True)
        used_by, used_at, kind = used.split("|")
        revoked_at = _text(await self._redis.get(_revoked_at(used_by)))
        return RefreshLookup(
            user_id=uuid.UUID(used_by),
            reused=True,
            used_at=_from_stamp(used_at),
            rotated=kind == "R",
            user_revoked_at=_from_stamp(revoked_at) if revoked_at else None,
        )

    async def revoke(self, jti: str, *, now: datetime) -> None:
        user_id = _text(await self._redis.getdel(_active(jti)))
        if user_id is not None:
            await self._mark_used(jti, user_id, now=now, rotated=False)
            await self._redis.set(_revoked_at(user_id), _stamp(now), ex=self._ttl)

    async def revoke_all(self, user_id: uuid.UUID, *, now: datetime) -> None:
        jtis = await self._redis.smembers(_user(user_id))
        async with self._redis.pipeline(transaction=True) as pipe:
            for jti in jtis:
                pipe.delete(_active(_text(jti) or ""))
            pipe.delete(_user(user_id))
            pipe.set(_revoked_at(user_id), _stamp(now), ex=self._ttl)
            await pipe.execute()

    async def _mark_used(self, jti: str, user_id: str, *, now: datetime, rotated: bool) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            value = f"{user_id}|{_stamp(now)}|{'R' if rotated else 'V'}"
            pipe.set(_used(jti), value, ex=self._ttl)
            pipe.srem(_user(user_id), jti)
            await pipe.execute()


class RedisOAuthStateStore:
    def __init__(self, redis: "Redis", *, ttl_seconds: int = 600) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def save(self, state: str, code_verifier: str) -> None:
        await self._redis.set(f"{_PREFIX}:oauth-state:{state}", code_verifier, ex=self._ttl)

    async def pop(self, state: str) -> str | None:
        return _text(await self._redis.getdel(f"{_PREFIX}:oauth-state:{state}"))

"""Redis 기반 refresh 토큰·OAuth state 저장소.

키:
- `oz:identity:refresh:<jti>` → user_id (활성 refresh, TTL = refresh 수명)
- `oz:identity:refresh-used:<jti>` → user_id
  (회전·폐기된 refresh, 재사용 탐지용, TTL = refresh 수명)
- `oz:identity:refresh-user:<user_id>` → jti 집합 (전체 폐기용)
- `oz:identity:oauth-state:<state>` → PKCE verifier (TTL 10분, 한 번만 사용)
"""

import uuid

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

    async def consume(self, jti: str) -> RefreshLookup | None:
        # GETDEL은 원자적이다. 같은 토큰으로 동시에 갱신하면 하나만 성공하고
        # 나머지는 재사용으로 판정된다 (프론트는 갱신 요청을 하나로 모아야 한다)
        user_id = _text(await self._redis.getdel(_active(jti)))
        if user_id is not None:
            await self._mark_used(jti, user_id)
            return RefreshLookup(user_id=uuid.UUID(user_id), reused=False)
        used_by = _text(await self._redis.get(_used(jti)))
        if used_by is not None:
            return RefreshLookup(user_id=uuid.UUID(used_by), reused=True)
        return None

    async def revoke(self, jti: str) -> None:
        user_id = _text(await self._redis.getdel(_active(jti)))
        if user_id is not None:
            await self._mark_used(jti, user_id)

    async def revoke_all(self, user_id: uuid.UUID) -> None:
        jtis = await self._redis.smembers(_user(user_id))
        async with self._redis.pipeline(transaction=True) as pipe:
            for jti in jtis:
                pipe.delete(_active(_text(jti) or ""))
            pipe.delete(_user(user_id))
            await pipe.execute()

    async def _mark_used(self, jti: str, user_id: str) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_used(jti), user_id, ex=self._ttl)
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

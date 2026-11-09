"""로그인 실패 잠금 (계획 P7, decisions A32): 이메일 기준 15분 안에 5회 실패하면 15분 잠금.

없는 이메일도 똑같이 센다(가입 여부를 드러내지 않기 위해). 키에는 이메일 대신 해시를 넣는다.
"""

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
LOCK_SECONDS = 15 * 60


def _digest(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()


class RedisLoginAttempts:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    @staticmethod
    def _failures(email: str) -> str:
        return f"oz:identity:login_fail:{_digest(email)}"

    @staticmethod
    def _lock(email: str) -> str:
        return f"oz:identity:login_lock:{_digest(email)}"

    async def locked_for(self, email: str) -> int:
        """잠겨 있으면 남은 초, 아니면 0."""
        ttl = int(await self._redis.ttl(self._lock(email)))
        return ttl if ttl > 0 else 0

    async def record_failure(self, email: str) -> int:
        """실패를 센다. 이번 실패로 잠기면 잠금 초, 아니면 0."""
        key = self._failures(email)
        count = int(await self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, WINDOW_SECONDS)
        if count < MAX_FAILURES:
            return 0
        await self._redis.set(self._lock(email), "1", ex=LOCK_SECONDS)
        await self._redis.delete(key)
        return LOCK_SECONDS

    async def clear(self, email: str) -> None:
        await self._redis.delete(self._failures(email), self._lock(email))

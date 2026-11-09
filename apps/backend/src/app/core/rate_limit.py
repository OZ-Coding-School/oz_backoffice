"""Redis 고정 창(fixed window) 레이트 리밋.

첫 요청 때 창(window)을 시작하고, 창 안에서 `limit`회를 넘으면 거부한다. 거부할 때는 창이 끝날
때까지 남은 초를 돌려준다. 키는 `oz:ratelimit:<이름>:<대상 해시>`.
"""

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after: int  # 거부됐을 때 다시 시도할 수 있기까지 초


class RedisRateLimiter:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def hit(
        self, name: str, subject: str, *, limit: int, window_seconds: int
    ) -> RateLimitResult:
        key = f"oz:ratelimit:{name}:{hashlib.sha256(subject.encode()).hexdigest()}"
        count = int(await self._redis.incr(key))
        if count == 1:
            await self._redis.expire(key, window_seconds)
        if count <= limit:
            return RateLimitResult(allowed=True, retry_after=0)
        ttl = int(await self._redis.ttl(key))
        if ttl < 0:  # 만료 시각이 없으면(경합 등) 다시 건다
            await self._redis.expire(key, window_seconds)
            ttl = window_seconds
        return RateLimitResult(allowed=False, retry_after=ttl)

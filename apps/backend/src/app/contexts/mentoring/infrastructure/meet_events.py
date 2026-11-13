"""처리한 Meet 이벤트 ID (Redis, 7일, A49)."""

from redis.asyncio import Redis

KEY = "oz:mentoring:meet_event:{}"
TTL_SECONDS = 7 * 24 * 3600  # Pub/Sub 구독 메시지 보관 기간과 같다


class RedisProcessedEvents:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def seen(self, event_id: str) -> bool:
        return bool(await self._redis.exists(KEY.format(event_id)))

    async def mark(self, event_id: str) -> None:
        await self._redis.set(KEY.format(event_id), "1", ex=TTL_SECONDS)

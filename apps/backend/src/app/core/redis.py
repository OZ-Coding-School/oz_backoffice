"""Redis 클라이언트."""

from typing import cast

from fastapi import Request
from redis.asyncio import Redis


def create_redis(url: str) -> "Redis":
    return Redis.from_url(url, decode_responses=True)


def get_redis(request: Request) -> "Redis":
    """FastAPI 의존성: lifespan에서 app.state.redis에 올려둔 클라이언트를 반환한다."""
    return cast("Redis", request.app.state.redis)

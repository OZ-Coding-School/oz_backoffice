"""헬스체크: /health (프로세스 생존), /health/ready (DB·Redis 연결)."""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from tortoise import Tortoise

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

Probe = Callable[[], Awaitable[None]]
CheckStatus = Literal["ok", "error"]


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


def get_database_probe() -> Probe:
    async def probe() -> None:
        await Tortoise.get_connection("default").execute_query("SELECT 1")

    return probe


def get_redis_probe(redis: Annotated[Redis, Depends(get_redis)]) -> Probe:
    async def probe() -> None:
        await redis.ping()

    return probe


@router.get("/health", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    database: Annotated[Probe, Depends(get_database_probe)],
    redis: Annotated[Probe, Depends(get_redis_probe)],
) -> ReadinessResponse:
    checks: dict[str, CheckStatus] = {}
    for name, probe in (("database", database), ("redis", redis)):
        try:
            await probe()
            checks[name] = "ok"
        except Exception:
            logger.warning("readiness 체크 실패: %s", name, exc_info=True)
            checks[name] = "error"
    ready = all(value == "ok" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if ready else "error", checks=checks)

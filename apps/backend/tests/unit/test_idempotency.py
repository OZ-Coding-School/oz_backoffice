"""요청 ID 중복 방지 (Redis)."""

import hashlib

import pytest
from fakeredis import FakeAsyncRedis
from pydantic import BaseModel

from app.core.idempotency import RedisIdempotency
from app.shared.errors import BusinessRuleViolation, ConflictError

pytestmark = pytest.mark.unit


class Out(BaseModel):
    value: int


async def test_same_key_runs_once_and_failure_releases_key() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    idem = RedisIdempotency(redis)
    calls = 0

    async def call() -> Out:
        nonlocal calls
        calls += 1
        return Out(value=calls)

    assert await idem.run("grant:u1", "k1", Out, call) == Out(value=1)
    assert await idem.run("grant:u1", "k1", Out, call) == Out(value=1)  # 저장된 응답
    assert await idem.run("grant:u2", "k1", Out, call) == Out(value=2)  # 범위가 다르면 별개
    assert calls == 2

    async def fail() -> Out:
        raise BusinessRuleViolation("실패", code="x")

    with pytest.raises(BusinessRuleViolation):
        await idem.run("grant:u1", "k2", Out, fail)
    assert await idem.run("grant:u1", "k2", Out, call) == Out(value=3)  # 실패 뒤 재시도 가능

    key = "oz:idempotency:grant:u1:" + hashlib.sha256(b"k3").hexdigest()
    await redis.set(key, "__pending__")
    with pytest.raises(ConflictError) as busy:
        await idem.run("grant:u1", "k3", Out, call)
    assert busy.value.code == "request_in_progress"
    await redis.aclose()

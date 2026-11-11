"""요청 ID(Idempotency-Key)로 같은 요청을 한 번만 처리한다 (Redis, decisions A39).

- 처음 온 요청은 키를 '처리 중'으로 잡고 실행한 뒤 응답을 24시간 보관한다.
- 같은 키로 다시 오면 저장된 응답을 그대로 돌려준다(다시 실행하지 않음).
- 처리 중에 같은 키가 또 오면 409 `request_in_progress`.
- 실행이 실패하면 키를 지워 다시 시도할 수 있게 한다.
키는 `oz:idempotency:<범위>:<요청 ID 해시>`. 범위에는 요청자와 엔드포인트를 넣는다.
"""

import hashlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.shared.errors import ConflictError

if TYPE_CHECKING:
    from redis.asyncio import Redis

RESULT_TTL_SECONDS = 24 * 60 * 60
PENDING_TTL_SECONDS = 60
_PENDING = "__pending__"


class RedisIdempotency:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def run[T: BaseModel](
        self,
        scope: str,
        key: str,
        response_type: type[T],
        call: Callable[[], Awaitable[T]],
    ) -> T:
        redis_key = f"oz:idempotency:{scope}:{hashlib.sha256(key.encode()).hexdigest()}"
        if not await self._redis.set(redis_key, _PENDING, nx=True, ex=PENDING_TTL_SECONDS):
            stored = await self._redis.get(redis_key)
            if stored is None or stored == _PENDING:
                raise ConflictError(
                    "같은 요청을 처리하고 있습니다. 잠시 후 다시 확인하세요.",
                    code="request_in_progress",
                )
            return response_type.model_validate_json(stored)
        try:
            result = await call()
        except BaseException:
            await self._redis.delete(redis_key)
            raise
        await self._redis.set(redis_key, result.model_dump_json(), ex=RESULT_TTL_SECONDS)
        return result

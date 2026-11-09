"""Redis 기반 명단 동기화 락.

키 (`oz:lock:<작업>`, plan §2.5):
- `oz:lock:roster-sync:all` — 전체 동기화
- `oz:lock:roster-sync:bootcamp:<id>` — 과정·기수 동기화 (기수 동기화도 과정 단위로 잠근다)

각 실행은 자기 키를 SET NX로 잡은 뒤 충돌하는 키가 있는지 확인하고, 있으면 자기 키를 지운다.
두 실행이 동시에 들어와도 둘 다 성공하지는 않는다(둘 다 실패할 수는 있다 → 409 후 재시도).
API가 잡고 워커가 놓으므로, 워커가 죽는 경우를 대비해 TTL을 둔다.
"""

import uuid

from redis.asyncio import Redis

from app.contexts.academy.domain.enums import RosterSyncScope

_ALL = "oz:lock:roster-sync:all"
_BOOTCAMP = "oz:lock:roster-sync:bootcamp:"
DEFAULT_TTL_SECONDS = 30 * 60


def _key(scope_type: RosterSyncScope, bootcamp_id: uuid.UUID | None) -> str:
    if scope_type is RosterSyncScope.ALL:
        return _ALL
    if bootcamp_id is None:
        raise ValueError("과정·기수 동기화 락에는 과정 ID가 필요합니다.")
    return f"{_BOOTCAMP}{bootcamp_id}"


class RedisRosterSyncLock:
    def __init__(self, redis: "Redis", *, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def acquire(self, scope_type: RosterSyncScope, bootcamp_id: uuid.UUID | None) -> bool:
        key = _key(scope_type, bootcamp_id)
        if not await self._redis.set(key, "1", nx=True, ex=self._ttl):
            return False
        if await self._has_conflict(scope_type):
            await self._redis.delete(key)
            return False
        return True

    async def release(self, scope_type: RosterSyncScope, bootcamp_id: uuid.UUID | None) -> None:
        await self._redis.delete(_key(scope_type, bootcamp_id))

    async def _has_conflict(self, scope_type: RosterSyncScope) -> bool:
        if scope_type is not RosterSyncScope.ALL:
            return bool(await self._redis.exists(_ALL))
        async for _ in self._redis.scan_iter(match=f"{_BOOTCAMP}*", count=100):
            return True
        return False

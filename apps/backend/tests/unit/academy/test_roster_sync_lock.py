import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.academy.domain.enums import RosterSyncScope
from app.contexts.academy.infrastructure.roster_sync_lock import RedisRosterSyncLock
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

ALL, BOOTCAMP, COHORT = RosterSyncScope.ALL, RosterSyncScope.BOOTCAMP, RosterSyncScope.COHORT


async def test_all_and_bootcamp_locks_exclude_each_other(fake_redis: FakeAsyncRedis) -> None:
    lock = RedisRosterSyncLock(fake_redis)
    a, b = new_id(), new_id()

    assert await lock.acquire(BOOTCAMP, a)
    assert not await lock.acquire(COHORT, a)  # 같은 과정의 기수 동기화
    assert await lock.acquire(COHORT, b)  # 다른 과정은 가능
    assert not await lock.acquire(ALL, None)  # 과정 동기화가 있으면 전체는 불가

    await lock.release(BOOTCAMP, a)
    await lock.release(COHORT, b)
    assert await lock.acquire(ALL, None)
    assert not await lock.acquire(BOOTCAMP, a)  # 전체 실행 중에는 모두 불가
    assert not await lock.acquire(ALL, None)
    await lock.release(ALL, None)
    assert await lock.acquire(BOOTCAMP, a)


async def test_failed_acquire_leaves_no_key(fake_redis: FakeAsyncRedis) -> None:
    lock = RedisRosterSyncLock(fake_redis)
    a = new_id()
    assert await lock.acquire(ALL, None)
    assert not await lock.acquire(BOOTCAMP, a)
    await lock.release(ALL, None)
    assert await fake_redis.keys("oz:lock:roster-sync:*") == []


async def test_lock_has_ttl(fake_redis: FakeAsyncRedis) -> None:
    lock = RedisRosterSyncLock(fake_redis, ttl_seconds=60)
    assert await lock.acquire(ALL, None)
    assert 0 < await fake_redis.ttl("oz:lock:roster-sync:all") <= 60


async def test_bootcamp_scope_requires_id(fake_redis: FakeAsyncRedis) -> None:
    with pytest.raises(ValueError, match="과정 ID"):
        await RedisRosterSyncLock(fake_redis).acquire(BOOTCAMP, None)

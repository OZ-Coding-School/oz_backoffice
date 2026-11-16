"""채팅 실시간 알림 Redis 어댑터 (fakeredis, A58)."""

import asyncio

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.mentoring.domain.chat import ChatEvent, ChatEventKind
from app.contexts.mentoring.infrastructure.chat_events import RedisChatEvents, channel_of, decode
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


async def test_publish_reaches_only_that_users_subscription() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    events = RedisChatEvents(redis)
    me, other = new_id(), new_id()
    stream = events.subscribe(me, idle_seconds=0.05)
    assert await anext(stream) is None  # 구독 시작, 아직 알림 없음 → 연결 유지 신호
    event = ChatEvent(ChatEventKind.MESSAGE, new_id(), new_id())
    await events.publish([me, me, other], event)
    await events.publish([other], ChatEvent(ChatEventKind.READ, new_id()))
    received = await asyncio.wait_for(anext(stream), timeout=1)
    assert received == event
    assert await anext(stream) is None  # 다른 사람 알림은 오지 않는다
    await redis.publish(channel_of(me), "not-json")  # 깨진 알림은 건너뛴다
    assert await anext(stream) is None
    await stream.aclose()
    await redis.aclose()


def test_decode_rejects_unknown_payloads() -> None:
    assert decode('{"kind": "nope", "thread_id": "x"}') is None
    assert decode("{}") is None

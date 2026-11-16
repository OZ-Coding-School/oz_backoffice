"""채팅 실시간 알림: Redis Pub/Sub (decisions A57·A58).

사용자마다 채널 `oz:mentoring:chat:user:<user_id>`에 알림(종류·방·메시지 ID)을 보낸다.
API 프로세스가 여러 개여도 그 사용자의 SSE 연결이 붙은 프로세스가 받는다.
놓친 알림은 다시 보내지 않는다.
"""

import json
import uuid
from collections.abc import AsyncGenerator, Iterable
from typing import Any

from redis.asyncio import Redis

from app.contexts.mentoring.domain.chat import ChatEvent, ChatEventKind

CHANNEL = "oz:mentoring:chat:user:{}"


def channel_of(user_id: uuid.UUID) -> str:
    return CHANNEL.format(user_id)


def encode(event: ChatEvent) -> str:
    return json.dumps(
        {
            "kind": event.kind.value,
            "thread_id": str(event.thread_id),
            "message_id": str(event.message_id) if event.message_id else None,
        }
    )


def decode(data: str) -> ChatEvent | None:
    try:
        raw = json.loads(data)
        return ChatEvent(
            kind=ChatEventKind(raw["kind"]),
            thread_id=uuid.UUID(raw["thread_id"]),
            message_id=uuid.UUID(raw["message_id"]) if raw.get("message_id") else None,
        )
    except (ValueError, KeyError, TypeError):
        return None


class RedisChatEvents:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def publish(self, user_ids: Iterable[uuid.UUID], event: ChatEvent) -> None:
        payload = encode(event)
        for user_id in set(user_ids):
            await self._redis.publish(channel_of(user_id), payload)

    async def subscribe(
        self, user_id: uuid.UUID, *, idle_seconds: float
    ) -> AsyncGenerator[ChatEvent | None]:
        """알림을 차례로 낸다. idle_seconds 동안 없으면 None(연결 유지 신호를 보낼 때)."""
        pubsub: Any = self._redis.pubsub()
        await pubsub.subscribe(channel_of(user_id))
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=idle_seconds
                )
                if message is None:
                    yield None
                    continue
                event = decode(message["data"])
                if event is not None:
                    yield event
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

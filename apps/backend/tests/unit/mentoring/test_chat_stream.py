"""채팅 SSE 스트림 생성 (A58)."""

from collections.abc import AsyncGenerator

import pytest

from app.contexts.mentoring.domain.chat import ChatEvent, ChatEventKind
from app.contexts.mentoring.presentation.chat_router import chat_stream
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


async def test_stream_sends_ready_ping_frames_and_stops_on_disconnect() -> None:
    shown, hidden, after = (ChatEvent(ChatEventKind.MESSAGE, new_id(), new_id()) for _ in range(3))
    closed: list[bool] = []

    async def events() -> AsyncGenerator[ChatEvent | None]:
        try:
            for item in (None, shown, hidden, after):
                yield item
        finally:
            closed.append(True)

    async def render(event: ChatEvent) -> str | None:
        return None if event == hidden else f"event: message\ndata: {event.message_id}\n\n"

    checks = iter([False, False, False, True])

    async def disconnected() -> bool:
        return next(checks)

    frames = [f async for f in chat_stream(events(), render, disconnected)]
    assert frames == [
        "retry: 3000\nevent: ready\ndata: {}\n\n",
        ": ping\n\n",
        f"event: message\ndata: {shown.message_id}\n\n",
    ]  # 볼 수 없는 알림은 건너뛰고, 끊기면 멈춘다
    assert closed == [True]  # 구독을 닫는다

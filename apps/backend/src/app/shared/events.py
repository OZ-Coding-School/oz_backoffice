"""프로세스 내 도메인 이벤트 디스패처.

서비스가 커밋 후(UnitOfWork.on_commit) 애그리거트에서 꺼낸 이벤트를 발행한다.
작업 큐로 넘겨야 하는 처리는 핸들러에서 taskiq 태스크를 enqueue한다.
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable

from app.shared.domain import DomainEvent

Handler = Callable[[DomainEvent], Awaitable[None]]


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: defaultdict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, events: Iterable[DomainEvent]) -> None:
        for event in events:
            for event_type, handlers in self._handlers.items():
                if isinstance(event, event_type):
                    for handler in handlers:
                        await handler(event)

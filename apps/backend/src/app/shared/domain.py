"""도메인 모델 베이스 (순수 Python)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.shared.ids import new_id


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """애그리거트에서 발생한 사실. 커밋 후 디스패처가 핸들러에 전달한다."""

    occurred_at: datetime
    event_id: uuid.UUID = field(default_factory=new_id)


@dataclass(kw_only=True, eq=False)
class Entity:
    """식별자로 동등성을 판단하는 엔티티."""

    id: uuid.UUID = field(default_factory=new_id)

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and isinstance(other, Entity) and other.id == self.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))


@dataclass(kw_only=True, eq=False)
class AggregateRoot(Entity):
    """트랜잭션 일관성 경계. 상태 변경 시 도메인 이벤트를 기록한다."""

    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

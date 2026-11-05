from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.shared.domain import AggregateRoot, DomainEvent, Entity
from app.shared.events import EventDispatcher

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, tzinfo=UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class SomethingHappened(DomainEvent):
    name: str


@dataclass(kw_only=True, eq=False)
class Sample(AggregateRoot):
    name: str = "sample"

    def rename(self, name: str) -> None:
        self.name = name
        self.record(SomethingHappened(occurred_at=NOW, name=name))


def test_entity_equality_by_id() -> None:
    a = Sample()
    b = Sample(id=a.id, name="other")
    assert a == b
    assert a != Sample()
    assert len({a, b}) == 1
    assert a != Entity(id=a.id)


async def test_aggregate_events_are_pulled_once_and_dispatched() -> None:
    sample = Sample()
    sample.rename("renamed")

    received: list[str] = []

    async def handler(event: DomainEvent) -> None:
        assert isinstance(event, SomethingHappened)
        received.append(event.name)

    dispatcher = EventDispatcher()
    dispatcher.subscribe(SomethingHappened, handler)

    await dispatcher.publish(sample.pull_events())
    await dispatcher.publish(sample.pull_events())

    assert received == ["renamed"]

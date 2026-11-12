"""Meet 이벤트 어댑터: 메시지 파싱·구독·회의 기록·Pub/Sub (가짜 클라이언트, A49)."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis
from google.api_core import exceptions as google_exceptions
from google.apps import events_subscriptions_v1 as events
from google.apps.meet_v2 import types as meet

from app.contexts.mentoring.infrastructure.meet_events import RedisProcessedEvents
from app.core.config import Settings
from app.core.meet import build_meet_events_client, build_meet_listener
from app.integrations.google.meet import MeetUnavailableError
from app.integrations.google.meet_events import (
    CONFERENCE_STARTED,
    EVENT_TYPES,
    GoogleMeetEvents,
    MeetEventListener,
    parse_message,
)

pytestmark = pytest.mark.unit


def _error(kind: type[Exception], message: str) -> Exception:
    return kind(message)  # api_core 예외 생성자는 타입이 없다


class FakeApis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.existing: list[Any] = []
        self.errors: dict[str, Exception] = {}

    def _record(self, name: str, request: Any) -> None:
        self.calls.append((name, request))
        if name in self.errors:
            raise self.errors[name]

    async def list_subscriptions(self, *, request: Any) -> Any:
        self._record("list", request)
        return SimpleNamespace(subscriptions=self.existing)

    async def create_subscription(self, *, request: Any) -> Any:
        self._record("create", request)

    async def update_subscription(self, *, request: Any) -> Any:
        self._record("update", request)

    async def get_conference_record(self, *, request: Any) -> Any:
        self._record("record", request)
        return meet.ConferenceRecord(
            name=request.name,
            space="spaces/a",
            start_time=datetime(2026, 11, 20, 5, tzinfo=UTC),
        )


def _client(apis: FakeApis) -> GoogleMeetEvents:
    return GoogleMeetEvents(
        subscriptions=apis,
        conferences=apis,
        topic="projects/p/topics/t",
        organizer_user_id="123",
    )


class FakeMessage:
    def __init__(self, attributes: dict[str, str], payload: Any) -> None:
        self.attributes = attributes
        self.data = json.dumps(payload).encode()
        self.result: str | None = None

    def ack(self) -> None:
        self.result = "ack"

    def nack(self) -> None:
        self.result = "nack"


def test_parse_message() -> None:
    attrs = {"ce-id": "e1", "ce-type": CONFERENCE_STARTED}
    data = json.dumps({"conferenceRecord": {"name": "conferenceRecords/c1"}}).encode()
    event = parse_message(attrs, data)
    assert event is not None
    assert (event.event_id, event.conference_record_name) == ("e1", "conferenceRecords/c1")
    recording = parse_message(
        attrs,
        json.dumps({"recording": {"name": "conferenceRecords/c1/recordings/r"}}).encode(),
    )
    assert recording is not None
    assert recording.conference_record_name == "conferenceRecords/c1"
    assert parse_message({}, data) is None
    assert parse_message(attrs, b"not json") is None
    assert parse_message(attrs, b"{}") is None


async def test_subscription_create_then_renew() -> None:
    apis = FakeApis()
    client = _client(apis)
    assert await client.ensure_subscription() == "created"
    created = apis.calls[-1][1].subscription
    assert created.target_resource == "//cloudidentity.googleapis.com/users/123"
    assert list(created.event_types) == list(EVENT_TYPES)
    assert created.notification_endpoint.pubsub_topic == "projects/p/topics/t"
    assert created.payload_options.include_resource is False

    apis.existing = [
        events.Subscription(name="subscriptions/old", state=events.Subscription.State.SUSPENDED),
        events.Subscription(name="subscriptions/s1", state=events.Subscription.State.ACTIVE),
    ]
    assert await client.ensure_subscription() == "renewed"
    update = apis.calls[-1][1]
    assert (update.subscription.name, list(update.update_mask.paths)) == (
        "subscriptions/s1",
        ["ttl"],
    )

    apis.errors["list"] = _error(google_exceptions.PermissionDenied, "위임 없음")
    with pytest.raises(MeetUnavailableError):
        await client.ensure_subscription()


async def test_conference_record_and_pull() -> None:
    apis = FakeApis()
    client = _client(apis)
    record = await client.get_conference("conferenceRecords/c1")
    assert record is not None
    assert (record.space_name, record.start_time, record.end_time) == (
        "spaces/a",
        datetime(2026, 11, 20, 5, tzinfo=UTC),
        None,
    )
    apis.errors["record"] = _error(google_exceptions.NotFound, "없음")
    assert await client.get_conference("conferenceRecords/gone") is None


async def test_listener_acks_after_handler() -> None:
    import asyncio

    handled: list[str] = []

    async def handler(event: Any) -> None:
        if event.event_id == "bad":
            raise RuntimeError("큐 등록 실패")
        handled.append(event.event_id)

    class FakeSubscriber:
        def __init__(self) -> None:
            self.closed = False
            self.future = SimpleNamespace(cancelled=False)
            self.future.cancel = lambda: setattr(self.future, "cancelled", True)

        def subscribe(self, subscription: str, **kwargs: Any) -> Any:
            self.subscription = subscription
            return self.future

        def close(self) -> None:
            self.closed = True

    subscriber = FakeSubscriber()
    listener = MeetEventListener(
        subscriber, "projects/p/subscriptions/s", handler, timeout_seconds=5
    )
    listener.start()
    assert subscriber.subscription == "projects/p/subscriptions/s"
    attrs = {"ce-id": "e1", "ce-type": CONFERENCE_STARTED}
    body = {"conferenceRecord": {"name": "conferenceRecords/c1"}}
    good, bad, junk = (
        FakeMessage(attrs, body),
        FakeMessage({**attrs, "ce-id": "bad"}, body),
        FakeMessage({}, {}),
    )
    # 라이브러리처럼 다른 스레드에서 콜백을 부른다
    for message in (good, bad, junk):
        await asyncio.to_thread(listener.on_message, message)
    assert (good.result, bad.result, junk.result) == ("ack", "nack", "ack")
    assert handled == ["e1"]
    listener.stop()
    assert subscriber.future.cancelled
    assert subscriber.closed


async def test_redis_processed_events() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    processed = RedisProcessedEvents(redis)
    assert not await processed.seen("e1")
    await processed.mark("e1")
    assert await processed.seen("e1")
    assert 0 < await redis.ttl("oz:mentoring:meet_event:e1") <= 7 * 24 * 3600
    await redis.aclose()


async def test_events_client_needs_settings(settings: Settings) -> None:
    assert await build_meet_events_client(settings) is None
    on = settings.model_copy(update={"meet_driver": "google"})
    assert await build_meet_events_client(on) is None  # 키·토픽·주최 계정 ID 없음

    async def handler(event: Any) -> None:
        return None

    assert build_meet_listener(settings, handler) is None
    assert build_meet_listener(on, handler) is None  # 구독 없음
    with_sub = on.model_copy(update={"meet_pubsub_subscription": "projects/p/subscriptions/s"})
    assert build_meet_listener(with_sub, handler) is None  # 키 없음

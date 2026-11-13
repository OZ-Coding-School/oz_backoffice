"""Meet 이벤트 수신 어댑터: Workspace Events 구독, 회의 기록 조회, Pub/Sub pull (A47·A49).

- 구독: 주최 계정(`GMAIL_SENDER`) 하나를 대상으로(`//cloudidentity.googleapis.com/users/<ID>`) 회의
  시작·종료와 녹화·전사·스마트 메모 생성 이벤트를 Pub/Sub 토픽으로 받는다.
  위임(meetings.space.readonly).
  갱신은 ttl=0(최대 기간)으로 다시 설정한다. 구독 이름은 저장하지 않고 조회해서 찾는다.
- 회의 기록: 이벤트 본문에는 회의 기록 이름만 있어 공간·시작·종료 시각을 다시 조회한다.
- 수신: Pub/Sub streaming pull(`MeetEventListener`)을 worker 프로세스에서 연다(A50). 서비스 계정
  자신의 IAM 권한(위임 아님). 받은 이벤트는 콜백(작업 등록)이 성공하면 ack, 실패하면 nack한다.
주최 계정 사용자 ID는 설정(`MEET_ORGANIZER_USER_ID`)으로 받는다
(위임 토큰의 tokeninfo에는 사용자 ID가 없다, A51).
"""

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from google.api_core import exceptions as google_exceptions
from google.apps import events_subscriptions_v1 as events
from google.apps.meet_v2 import ConferenceRecordsServiceAsyncClient
from google.apps.meet_v2 import types as meet
from google.cloud import pubsub_v1  # type: ignore[import-untyped]  # 고수준 구독 클라이언트는 타입이 없다
from google.oauth2 import service_account

from app.integrations.google.meet import MeetUnavailableError

logger = logging.getLogger(__name__)

MEET_READONLY_SCOPE = "https://www.googleapis.com/auth/meetings.space.readonly"
PUBSUB_SCOPE = "https://www.googleapis.com/auth/pubsub"

CONFERENCE_STARTED = "google.workspace.meet.conference.v2.started"
CONFERENCE_ENDED = "google.workspace.meet.conference.v2.ended"
RECORDING_GENERATED = "google.workspace.meet.recording.v2.fileGenerated"
TRANSCRIPT_GENERATED = "google.workspace.meet.transcript.v2.fileGenerated"
SMART_NOTE_GENERATED = "google.workspace.meet.smartNote.v2.fileGenerated"
EVENT_TYPES = (
    CONFERENCE_STARTED,
    CONFERENCE_ENDED,
    RECORDING_GENERATED,
    TRANSCRIPT_GENERATED,
    SMART_NOTE_GENERATED,
)
_PAYLOAD_KEYS = ("conferenceRecord", "recording", "transcript", "smartNote")


@dataclass(frozen=True, slots=True)
class MeetEvent:
    event_id: str
    event_type: str
    resource_name: str  # conferenceRecords/X 또는 conferenceRecords/X/recordings/Y 등

    @property
    def conference_record_name(self) -> str:
        return "/".join(self.resource_name.split("/")[:2])


@dataclass(frozen=True, slots=True)
class ConferenceInfo:
    name: str
    space_name: str
    start_time: datetime | None
    end_time: datetime | None


def parse_message(attributes: dict[str, str], data: bytes) -> MeetEvent | None:
    """Workspace Events의 CloudEvents 메시지 → MeetEvent. 모르는 형식이면 None."""
    event_id, event_type = attributes.get("ce-id"), attributes.get("ce-type")
    if not event_id or not event_type:
        return None
    try:
        payload = json.loads(data or b"{}")
    except ValueError:
        return None
    for key in _PAYLOAD_KEYS:
        name = (payload.get(key) or {}).get("name") if isinstance(payload, dict) else None
        if isinstance(name, str) and name.startswith("conferenceRecords/"):
            return MeetEvent(event_id, event_type, name)
    return None


class SubscriptionsApi(Protocol):
    async def list_subscriptions(self, *, request: Any) -> Any: ...
    async def create_subscription(self, *, request: Any) -> Any: ...
    async def update_subscription(self, *, request: Any) -> Any: ...


class ConferencesApi(Protocol):
    async def get_conference_record(self, *, request: Any) -> Any: ...


def _datetime(value: Any) -> datetime | None:
    """proto-plus Timestamp(datetime 하위 타입) → UTC. 비어 있으면(없음·epoch) None."""
    if not isinstance(value, datetime) or value.timestamp() <= 0:
        return None
    return value.astimezone(UTC)


class GoogleMeetEvents:
    def __init__(
        self,
        *,
        subscriptions: SubscriptionsApi,
        conferences: ConferencesApi,
        topic: str,
        organizer_user_id: str,
    ) -> None:
        self._subscriptions = subscriptions
        self._conferences = conferences
        self._topic = topic
        self._target = f"//cloudidentity.googleapis.com/users/{organizer_user_id}"

    async def ensure_subscription(self) -> str:
        """주최 계정 구독이 있으면 갱신, 없으면 만든다. 'renewed' 또는 'created'."""
        try:
            found = await self._subscriptions.list_subscriptions(
                request=events.ListSubscriptionsRequest(
                    filter=f'event_types:"{CONFERENCE_STARTED}" AND '
                    f'target_resource="{self._target}"'
                )
            )
            active = [
                s
                for s in getattr(found, "subscriptions", [])
                if s.state == events.Subscription.State.ACTIVE
            ]
            if active:
                await self._subscriptions.update_subscription(
                    request=events.UpdateSubscriptionRequest(
                        subscription=events.Subscription(name=active[0].name, ttl={"seconds": 0}),
                        update_mask={"paths": ["ttl"]},
                    )
                )
                return "renewed"
            await self._subscriptions.create_subscription(
                request=events.CreateSubscriptionRequest(
                    subscription=events.Subscription(
                        target_resource=self._target,
                        event_types=list(EVENT_TYPES),
                        notification_endpoint=events.NotificationEndpoint(pubsub_topic=self._topic),
                        payload_options=events.PayloadOptions(include_resource=False),
                        ttl={"seconds": 0},
                    )
                )
            )
            return "created"
        except google_exceptions.GoogleAPICallError as exc:
            logger.warning("Meet 이벤트 구독 실패: %s", type(exc).__name__)
            raise MeetUnavailableError("Meet 이벤트 구독을 처리하지 못했습니다.") from exc

    async def get_conference(self, record_name: str) -> ConferenceInfo | None:
        try:
            record = await self._conferences.get_conference_record(
                request=meet.GetConferenceRecordRequest(name=record_name)
            )
        except google_exceptions.NotFound:
            return None
        except google_exceptions.GoogleAPICallError as exc:
            logger.warning("회의 기록 조회 실패(%s): %s", record_name, type(exc).__name__)
            raise MeetUnavailableError() from exc
        return ConferenceInfo(
            name=record.name,
            space_name=record.space,
            start_time=_datetime(record.start_time),
            end_time=_datetime(record.end_time),
        )


async def build_meet_events(
    service_account_info: dict[str, Any],
    organizer: str,
    *,
    topic: str,
    organizer_user_id: str,
) -> GoogleMeetEvents:
    delegated = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]  # google-auth 타입 없음
        service_account_info, scopes=[MEET_READONLY_SCOPE], subject=organizer
    )
    return GoogleMeetEvents(
        subscriptions=events.SubscriptionsServiceAsyncClient(credentials=delegated),
        conferences=ConferenceRecordsServiceAsyncClient(credentials=delegated),
        topic=topic,
        organizer_user_id=organizer_user_id,
    )


EventHandler = Callable[[MeetEvent], Coroutine[Any, Any, None]]


class MeetEventListener:
    """Pub/Sub streaming pull. 라이브러리가 자기 스레드에서 콜백을 부르므로, 이벤트 처리 코루틴은
    수신을 시작한 이벤트 루프로 넘겨 끝날 때까지 기다린 뒤 ack/nack한다."""

    def __init__(
        self,
        subscriber: Any,
        subscription: str,
        handler: EventHandler,
        *,
        timeout_seconds: float = 30,
        max_messages: int = 20,
    ) -> None:
        self._subscriber = subscriber
        self._subscription = subscription
        self._handler = handler
        self._timeout = timeout_seconds
        self._max_messages = max_messages
        self._loop: asyncio.AbstractEventLoop | None = None
        self._future: Any = None

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._future = self._subscriber.subscribe(
            self._subscription,
            callback=self.on_message,
            flow_control=pubsub_v1.types.FlowControl(max_messages=self._max_messages),
        )
        logger.info("Meet 이벤트 실시간 수신 시작")

    def stop(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None
        self._subscriber.close()

    def on_message(self, message: Any) -> None:
        """수신 스레드에서 불린다. 모르는 메시지는 ack, 처리 등록에 실패하면 nack(다시 받음)."""
        event = parse_message(dict(message.attributes), message.data)
        if event is None or self._loop is None:
            message.ack()
            return
        try:
            asyncio.run_coroutine_threadsafe(self._handler(event), self._loop).result(
                timeout=self._timeout
            )
        except Exception:  # 등록 실패는 다시 받도록 둔다 (수신 스레드를 죽이지 않는다)
            logger.warning("Meet 이벤트 등록 실패(%s), 다시 받는다", event.event_type)
            message.nack()
            return
        message.ack()


def build_listener(
    service_account_info: dict[str, Any], subscription: str, handler: EventHandler
) -> MeetEventListener:
    own = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]  # google-auth 타입 없음
        service_account_info, scopes=[PUBSUB_SCOPE]
    )
    return MeetEventListener(pubsub_v1.SubscriberClient(credentials=own), subscription, handler)

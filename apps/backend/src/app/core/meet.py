"""설정으로 Google Meet 클라이언트를 고른다 (decisions A48).

disabled이거나 서비스 계정 키·주최 계정(GMAIL_SENDER)이 없으면 None을 준다. 공간이 필요한 작업은
None이면 건너뛰고, 설정이 갖춰지면 주기 작업이 빠진 공간을 채운다.
"""

import logging

from app.core.config import Settings
from app.integrations.google.meet import GoogleMeetClient, build_spaces_api
from app.integrations.google.meet_events import (
    EventHandler,
    GoogleMeetEvents,
    MeetEventListener,
    build_listener,
    build_meet_events,
)
from app.integrations.notifications.mail import parse_service_account_json

logger = logging.getLogger(__name__)


def build_meet_client(settings: Settings) -> GoogleMeetClient | None:
    if settings.meet_driver != "google":
        return None
    info = parse_service_account_json(settings.google_service_account_json.get_secret_value())
    if info is None or not settings.gmail_sender:
        logger.warning(
            "Meet 비활성: MEET_DRIVER=google에는 "
            "GOOGLE_SERVICE_ACCOUNT_JSON과 GMAIL_SENDER가 필요합니다."
        )
        return None
    return GoogleMeetClient(build_spaces_api(info, settings.gmail_sender))


async def build_meet_events_client(settings: Settings) -> GoogleMeetEvents | None:
    """Meet이 켜져 있고 토픽·구독이 설정돼 있을 때만 만든다."""
    if settings.meet_driver != "google":
        return None
    info = parse_service_account_json(settings.google_service_account_json.get_secret_value())
    if info is None or not settings.gmail_sender or not settings.meet_pubsub_topic:
        logger.warning(
            "Meet 이벤트 구독 비활성: 서비스 계정 키·GMAIL_SENDER·MEET_PUBSUB_TOPIC이 필요합니다."
        )
        return None
    return await build_meet_events(
        info,
        settings.gmail_sender,
        topic=settings.meet_pubsub_topic,
        organizer_user_id=settings.meet_organizer_user_id,
    )


def build_meet_listener(settings: Settings, handler: EventHandler) -> MeetEventListener | None:
    """worker 시작 때 실시간 수신기를 만든다 (A50). 설정이 없으면 None."""
    if settings.meet_driver != "google" or not settings.meet_pubsub_subscription:
        return None
    info = parse_service_account_json(settings.google_service_account_json.get_secret_value())
    if info is None:
        logger.warning("Meet 이벤트 수신 비활성: 서비스 계정 키가 없습니다.")
        return None
    return build_listener(info, settings.meet_pubsub_subscription, handler)

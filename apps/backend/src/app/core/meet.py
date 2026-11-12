"""설정으로 Google Meet 클라이언트를 고른다 (decisions A48).

disabled이거나 서비스 계정 키·주최 계정(GMAIL_SENDER)이 없으면 None을 준다. 공간이 필요한 작업은
None이면 건너뛰고, 설정이 갖춰지면 주기 작업이 빠진 공간을 채운다.
"""

import logging

from app.core.config import Settings
from app.integrations.google.meet import GoogleMeetClient, build_spaces_api
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

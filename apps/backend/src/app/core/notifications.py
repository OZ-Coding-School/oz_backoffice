"""설정(Settings)으로 메일·SMS 발송 드라이버를 고른다.

- console: 개발용(로그 출력). 운영(environment=production)에서는 발송을 거부하는 드라이버로 바꾼다.
- gmail: 서비스 계정 JSON과 발신 계정이 없거나 JSON이 올바르지 않으면 발송을 거부한다.
거부 드라이버는 앱 기동을 막지 않고 발송 API만 503(`*_not_configured`)으로 실패시킨다.
"""

import logging

from app.core.config import Settings
from app.integrations.notifications.mail import (
    ConsoleMailSender,
    DisabledMailSender,
    GmailSender,
    MailSender,
    parse_service_account_json,
)
from app.integrations.notifications.sms import ConsoleSmsSender, DisabledSmsSender, SmsSender

logger = logging.getLogger(__name__)


def build_mail_sender(settings: Settings) -> MailSender:
    if settings.mail_driver == "console":
        if settings.environment == "production":
            return _disabled_mail("운영 환경에서는 console 메일 드라이버를 쓸 수 없습니다.")
        return ConsoleMailSender()
    info = parse_service_account_json(settings.google_service_account_json.get_secret_value())
    if info is None or not settings.gmail_sender:
        return _disabled_mail(
            "MAIL_DRIVER=gmail에는 GOOGLE_SERVICE_ACCOUNT_JSON(서비스 계정 키)과 "
            "GMAIL_SENDER가 필요합니다."
        )
    return GmailSender(
        service_account_info=info,
        sender=settings.gmail_sender,
        sender_name=settings.mail_sender_name,
    )


def build_sms_sender(settings: Settings) -> SmsSender:
    if settings.environment == "production":
        reason = "운영 환경에서는 console SMS 드라이버를 쓸 수 없습니다(SMS 업체 미정)."
        logger.warning("SMS 발송 비활성: %s", reason)
        return DisabledSmsSender(reason)
    return ConsoleSmsSender()


def _disabled_mail(reason: str) -> DisabledMailSender:
    logger.warning("메일 발송 비활성: %s", reason)
    return DisabledMailSender(reason)

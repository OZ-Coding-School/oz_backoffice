"""SMS 발송 (decisions A4). 업체가 정해지기 전에는 console(개발용 로그 출력) 드라이버만 있다.

업체 어댑터는 `SmsSender` Protocol을 구현해 별도 PR로 붙인다.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)


class SmsDeliveryError(ServiceUnavailableError):
    default_code = "sms_delivery_failed"


@dataclass(frozen=True, slots=True)
class SmsMessage:
    to: str  # 숫자만 (01012345678)
    text: str


class SmsSender(Protocol):
    async def send(self, message: SmsMessage) -> None: ...


def mask_phone(phone: str) -> str:
    """로그용: 가운데를 가린다. 01012345678 → 010****5678"""
    return f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 8 else "***"


class ConsoleSmsSender:
    """개발용: 문자를 보내지 않고 로그로 출력한다(받는 번호는 가린다)."""

    async def send(self, message: SmsMessage) -> None:
        logger.info("[SMS 콘솔 드라이버] 받는 번호=%s %s", mask_phone(message.to), message.text)


class DisabledSmsSender:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def send(self, message: SmsMessage) -> None:
        raise SmsDeliveryError(
            "문자 발송이 설정되지 않았습니다. 관리자에게 문의하세요.", code="sms_not_configured"
        )

"""메일 발송 (decisions A4). 드라이버: console(개발용 로그 출력), gmail(Gmail API).

Gmail은 서비스 계정 + 도메인 전체 위임으로 발신 계정(`subject`)을 대신해 보낸다(A8, 범위
`gmail.send`). google-api-python-client는 동기 라이브러리라 `asyncio.to_thread`로 호출한다.
발송 실패는 `MailDeliveryError`(503)로 바꿔 올린다.
"""

import asyncio
import base64
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from typing import Any, Protocol

from app.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class MailDeliveryError(ServiceUnavailableError):
    default_code = "mail_delivery_failed"


@dataclass(frozen=True, slots=True)
class MailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None


class MailSender(Protocol):
    async def send(self, message: MailMessage) -> None: ...


def mask_email(address: str) -> str:
    """로그용: 앞 1글자만 남긴다. kim@gmail.com → k***@gmail.com"""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def build_mime(message: MailMessage, *, sender: str, sender_name: str) -> EmailMessage:
    """텍스트 본문 + (있으면) HTML 대체 본문. 한글 제목·표시 이름은 표준 인코딩된다."""
    mime = EmailMessage()
    local, _, domain = sender.partition("@")
    mime["From"] = Address(display_name=sender_name, username=local, domain=domain)
    mime["To"] = message.to
    mime["Subject"] = message.subject
    mime.set_content(message.text)
    if message.html is not None:
        mime.add_alternative(message.html, subtype="html")
    return mime


class ConsoleMailSender:
    """개발용: 메일을 보내지 않고 로그로 출력한다(받는 주소는 가린다)."""

    async def send(self, message: MailMessage) -> None:
        logger.info(
            "[메일 콘솔 드라이버] 받는 사람=%s 제목=%s\n%s",
            mask_email(message.to),
            message.subject,
            message.text,
        )


class DisabledMailSender:
    """발송을 쓸 수 없는 설정(운영의 console, gmail 설정 누락)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def send(self, message: MailMessage) -> None:
        raise MailDeliveryError(
            "메일 발송이 설정되지 않았습니다. 관리자에게 문의하세요.", code="mail_not_configured"
        )


# 서비스 계정 정보·발신 계정 → Gmail API 서비스 객체 (테스트에서 바꿔 끼운다)
GmailServiceFactory = Callable[[dict[str, Any], str], Any]


def _build_gmail_service(info: dict[str, Any], subject: str) -> Any:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    # google-auth의 이 생성 함수에는 타입 주석이 없다(스텁 대상 아님)
    credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
        info, scopes=[GMAIL_SEND_SCOPE], subject=subject
    )
    # 라이브러리에 포함된 discovery 문서를 쓴다(네트워크 조회·파일 캐시 없음)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


class GmailSender:
    def __init__(
        self,
        *,
        service_account_info: dict[str, Any],
        sender: str,
        sender_name: str,
        service_factory: GmailServiceFactory = _build_gmail_service,
    ) -> None:
        self._info = service_account_info
        self._sender = sender
        self._sender_name = sender_name
        self._service_factory = service_factory

    async def send(self, message: MailMessage) -> None:
        mime = build_mime(message, sender=self._sender, sender_name=self._sender_name)
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        try:
            await asyncio.to_thread(self._send_raw, raw)
        except (
            Exception
        ) as exc:  # 라이브러리 예외(HttpError, RefreshError, 연결 오류)를 한곳에서 바꾼다
            logger.warning(
                "Gmail 발송 실패 (받는 사람=%s): %s", mask_email(message.to), type(exc).__name__
            )
            raise MailDeliveryError("메일을 보내지 못했습니다. 잠시 후 다시 시도하세요.") from exc

    def _send_raw(self, raw: str) -> None:
        # httplib2 기반 서비스 객체는 스레드 간에 공유하지 않으므로 발송마다 만든다
        service = self._service_factory(self._info, self._sender)
        service.users().messages().send(userId="me", body={"raw": raw}).execute()


def parse_service_account_json(raw: str) -> dict[str, Any] | None:
    """환경변수의 서비스 계정 JSON 원문. 비었거나 형식이 다르면 None."""
    if not raw.strip():
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(info, dict) or info.get("type") != "service_account":
        return None
    return info

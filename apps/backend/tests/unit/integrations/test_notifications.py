import base64
import email
import json
import logging
from email.header import decode_header, make_header
from typing import Any

import pytest

from app.core.config import Settings
from app.core.notifications import build_mail_sender, build_sms_sender
from app.integrations.notifications.mail import (
    ConsoleMailSender,
    DisabledMailSender,
    GmailSender,
    MailDeliveryError,
    MailMessage,
    build_mime,
    mask_email,
    parse_service_account_json,
)
from app.integrations.notifications.sms import (
    ConsoleSmsSender,
    DisabledSmsSender,
    SmsDeliveryError,
    SmsMessage,
    mask_phone,
)

pytestmark = pytest.mark.unit

MESSAGE = MailMessage(
    to="kim@gmail.com",
    subject="[오즈코딩스쿨] 이메일 인증코드 123456",
    text="인증코드: 123456",
    html="<p>인증코드: <b>123456</b></p>",
)
SERVICE_ACCOUNT = {"type": "service_account", "client_email": "mailer@p.iam.gserviceaccount.com"}


def _decoded(header: str) -> str:
    return str(make_header(decode_header(header)))


def test_build_mime_has_text_and_html_with_korean_headers() -> None:
    mime = build_mime(MESSAGE, sender="ops@nextrunners.co.kr", sender_name="오즈코딩스쿨")
    parsed = email.message_from_bytes(mime.as_bytes())

    assert _decoded(parsed["From"]) == "오즈코딩스쿨 <ops@nextrunners.co.kr>"
    assert _decoded(parsed["Subject"]) == MESSAGE.subject
    assert parsed["To"] == "kim@gmail.com"
    assert parsed.get_content_type() == "multipart/alternative"
    parts = {part.get_content_type(): part.get_payload(decode=True) for part in parsed.walk()}
    assert isinstance(parts["text/plain"], bytes)
    assert isinstance(parts["text/html"], bytes)
    assert "123456" in parts["text/plain"].decode()
    assert "<b>123456</b>" in parts["text/html"].decode()


def test_text_only_message() -> None:
    mime = build_mime(
        MailMessage(to="a@gmail.com", subject="제목", text="본문"),
        sender="ops@nextrunners.co.kr",
        sender_name="오즈",
    )
    assert mime.get_content_type() == "text/plain"


class FakeGmailService:
    """googleapiclient 서비스 객체의 users().messages().send(...).execute() 흉내."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error

    def users(self) -> "FakeGmailService":
        return self

    def messages(self) -> "FakeGmailService":
        return self

    def send(self, **kwargs: Any) -> "FakeGmailService":
        self.calls.append(kwargs)
        return self

    def execute(self) -> dict[str, str]:
        if self.error:
            raise self.error
        return {"id": "msg-1"}


async def test_gmail_sender_impersonates_sender_and_sends_raw_mime() -> None:
    service = FakeGmailService()
    created: list[tuple[dict[str, Any], str]] = []

    def factory(info: dict[str, Any], subject: str) -> FakeGmailService:
        created.append((info, subject))
        return service

    sender = GmailSender(
        service_account_info=SERVICE_ACCOUNT,
        sender="ops@nextrunners.co.kr",
        sender_name="오즈코딩스쿨",
        service_factory=factory,
    )
    await sender.send(MESSAGE)

    assert created == [(SERVICE_ACCOUNT, "ops@nextrunners.co.kr")]  # 위임 대상 = 발신 계정
    call = service.calls[0]
    assert call["userId"] == "me"
    raw = base64.urlsafe_b64decode(call["body"]["raw"])
    assert _decoded(email.message_from_bytes(raw)["Subject"]) == MESSAGE.subject


async def test_gmail_failure_becomes_delivery_error(caplog: pytest.LogCaptureFixture) -> None:
    sender = GmailSender(
        service_account_info=SERVICE_ACCOUNT,
        sender="ops@nextrunners.co.kr",
        sender_name="오즈",
        service_factory=lambda info, subject: FakeGmailService(RuntimeError("unauthorized")),
    )
    with caplog.at_level(logging.WARNING), pytest.raises(MailDeliveryError) as exc:
        await sender.send(MESSAGE)
    assert exc.value.code == "mail_delivery_failed"
    assert "kim@gmail.com" not in caplog.text  # 받는 주소를 로그에 남기지 않는다


async def test_console_drivers_mask_recipients(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        await ConsoleMailSender().send(MESSAGE)
        await ConsoleSmsSender().send(SmsMessage(to="01012345678", text="인증번호 123456"))
    assert "k***@gmail.com" in caplog.text
    assert "010****5678" in caplog.text
    assert "kim@gmail.com" not in caplog.text
    assert "01012345678" not in caplog.text
    assert "123456" in caplog.text  # 개발용이라 코드는 보인다


def test_masks() -> None:
    assert mask_email("kim@gmail.com") == "k***@gmail.com"
    assert mask_email("broken") == "***"
    assert mask_phone("01012345678") == "010****5678"
    assert mask_phone("123") == "***"


def test_parse_service_account_json() -> None:
    assert parse_service_account_json(json.dumps(SERVICE_ACCOUNT)) == SERVICE_ACCOUNT
    assert parse_service_account_json("") is None
    assert parse_service_account_json("{not json") is None
    assert parse_service_account_json(json.dumps({"type": "authorized_user"})) is None


def _settings(settings: Settings, **update: Any) -> Settings:
    return settings.model_copy(update=update)


async def test_driver_selection(settings: Settings) -> None:
    assert isinstance(build_mail_sender(settings), ConsoleMailSender)
    assert isinstance(build_sms_sender(settings), ConsoleSmsSender)

    from pydantic import SecretStr

    gmail = _settings(
        settings,
        mail_driver="gmail",
        gmail_sender="ops@nextrunners.co.kr",
        google_service_account_json=SecretStr(json.dumps(SERVICE_ACCOUNT)),
    )
    assert isinstance(build_mail_sender(gmail), GmailSender)
    missing = _settings(settings, mail_driver="gmail")
    assert isinstance(build_mail_sender(missing), DisabledMailSender)


async def test_production_refuses_console_drivers(settings: Settings) -> None:
    production = _settings(settings, environment="production")
    mail = build_mail_sender(production)
    sms = build_sms_sender(production)

    with pytest.raises(MailDeliveryError) as mail_error:
        await mail.send(MESSAGE)
    assert mail_error.value.code == "mail_not_configured"
    with pytest.raises(SmsDeliveryError) as sms_error:
        await sms.send(SmsMessage(to="01012345678", text="x"))
    assert sms_error.value.code == "sms_not_configured"
    assert isinstance(sms, DisabledSmsSender)

"""메모리 발송 드라이버: 보낸 메일·문자를 모아 테스트에서 검증한다."""

from app.integrations.notifications.mail import MailMessage
from app.integrations.notifications.sms import SmsMessage


class InMemoryMailSender:
    def __init__(self) -> None:
        self.sent: list[MailMessage] = []

    async def send(self, message: MailMessage) -> None:
        self.sent.append(message)


class InMemorySmsSender:
    def __init__(self) -> None:
        self.sent: list[SmsMessage] = []

    async def send(self, message: SmsMessage) -> None:
        self.sent.append(message)

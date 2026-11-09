import pytest

from app.integrations.notifications.mail import MailDeliveryError, MailMessage
from app.workers.tasks import notifications
from app.workers.tasks.notifications import deliver_with_retry, send_mail

pytestmark = pytest.mark.unit

MESSAGE = MailMessage(to="kim@gmail.com", subject="제목", text="본문")


class FlakySender:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def send(self, message: MailMessage) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise MailDeliveryError("실패")


@pytest.mark.parametrize(
    ("failures", "delivered", "calls"), [(0, True, 1), (2, True, 3), (5, False, 3)]
)
async def test_retries_up_to_three_times(
    monkeypatch: pytest.MonkeyPatch, failures: int, delivered: bool, calls: int
) -> None:
    sender = FlakySender(failures)
    monkeypatch.setattr(notifications, "build_mail_sender", lambda settings: sender)

    assert await deliver_with_retry(MESSAGE, delays=(0, 0)) is delivered
    assert sender.calls == calls


def test_task_is_registered() -> None:
    assert send_mail.task_name == "notifications.send_mail"

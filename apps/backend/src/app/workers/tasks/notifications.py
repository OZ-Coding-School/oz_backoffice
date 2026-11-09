"""알림 메일 발송 작업 (decisions A30·A31).

승인·반려 알림처럼 처리 결과와 별개인 메일은 커밋 후 이 작업으로 보낸다. 실패하면 최대 3회
시도하고(간격 5초·30초), 끝내 실패해도 처리(승인·반려)는 되돌리지 않고 로그만 남긴다.
인증코드처럼 즉시성이 중요한 메일은 요청 안에서 바로 보낸다(A29).
"""

import asyncio
import logging

from app.core.config import get_settings
from app.core.notifications import build_mail_sender
from app.integrations.notifications.mail import MailMessage, mask_email
from app.shared.errors import ServiceUnavailableError
from app.workers.broker import broker

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (5, 30)


async def deliver_with_retry(
    message: MailMessage, *, delays: tuple[int, ...] = RETRY_DELAYS_SECONDS
) -> bool:
    sender = build_mail_sender(get_settings())
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await sender.send(message)
            return True
        except ServiceUnavailableError as exc:
            logger.warning(
                "알림 메일 발송 실패 %d/%d (받는 사람=%s): %s",
                attempt,
                MAX_ATTEMPTS,
                mask_email(message.to),
                exc.code,
            )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(delays[min(attempt - 1, len(delays) - 1)])
    return False


@broker.task(task_name="notifications.send_mail")
async def send_mail(to: str, subject: str, text: str, html: str | None = None) -> None:
    await deliver_with_retry(MailMessage(to=to, subject=subject, text=text, html=html))


class TaskiqMailDispatcher:
    """알림 메일을 워커로 보낸다. app.main이 app.state.mail_dispatcher에 연결한다."""

    async def dispatch(self, message: MailMessage) -> None:
        await send_mail.kiq(message.to, message.subject, message.text, message.html)

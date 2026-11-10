"""가입 승인·반려 알림 메일 (decisions A30·A31).

커밋 후 워커로 보낸다. 이름·사유는 HTML 이스케이프한다.
"""

import html

from app.contexts.identity.domain.entities import User
from app.integrations.notifications.mail import MailMessage


def approval_mail(user: User, *, sender_name: str, login_url: str) -> MailMessage:
    name, url = html.escape(user.name), html.escape(login_url, quote=True)
    return MailMessage(
        to=user.email,
        subject=f"[{sender_name}] 가입이 승인되었습니다",
        text=(
            f"{user.name}님, {sender_name} 가입이 승인되었습니다.\n"
            f"아래 주소에서 로그인해 주세요.\n{login_url}"
        ),
        html=(
            f"<p>{name}님, {sender_name} 가입이 승인되었습니다.</p>"
            f'<p><a href="{url}">로그인하기</a></p>'
        ),
    )


def rejection_mail(user: User, reason: str, *, sender_name: str, login_url: str) -> MailMessage:
    name, url = html.escape(user.name), html.escape(login_url, quote=True)
    return MailMessage(
        to=user.email,
        subject=f"[{sender_name}] 가입 신청이 반려되었습니다",
        text=(
            f"{user.name}님, {sender_name} 가입 신청이 반려되었습니다.\n"
            f"사유: {reason}\n"
            f"로그인해 신청 정보를 확인하고 다시 신청할 수 있습니다.\n{login_url}"
        ),
        html=(
            f"<p>{name}님, {sender_name} 가입 신청이 반려되었습니다.</p>"
            f"<p>사유: {html.escape(reason)}</p>"
            "<p>로그인해 신청 정보를 확인하고 다시 신청할 수 있습니다.</p>"
            f'<p><a href="{url}">로그인하기</a></p>'
        ),
    )

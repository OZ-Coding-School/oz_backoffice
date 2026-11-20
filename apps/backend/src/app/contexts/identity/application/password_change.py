"""내 정보 비밀번호 변경 (링크 인증, decisions A72).

1. 링크 요청: 비밀번호가 있는 회원만. 1분 간격·하루 5회. 새 링크를 보내면 전 링크는 무효.
2. 링크 확인: 30분 안·한 번만. 확인하면 10분 동안 새 비밀번호를 저장할 수 있다.
3. 상태 조회: 내 정보 화면이 5초마다 확인한다.
4. 변경: 인증된 10분 안에만. 규칙은 가입과 같고, 세션은 유지하며 로그인 잠금을 푼다(A32와 같음).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.password_auth import LoginAttempts, PasswordHasher
from app.contexts.identity.application.verification_codes import RateLimiter, seconds
from app.contexts.identity.domain.credentials import validate_password
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.password_change import (
    LINK_DAILY_LIMIT,
    LINK_RESEND_INTERVAL,
    LINK_TTL,
    PasswordChangeLink,
    PasswordChangeState,
    PasswordChangeStore,
)
from app.contexts.identity.domain.repositories import UserRepository
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailMessage, MailSender
from app.shared.errors import BusinessRuleViolation, TooManyRequestsError

LINK_LIMIT_NAME = "password_change_link"
DAY_SECONDS = 24 * 60 * 60
VERIFY_PATH = "/password-change/verify"


@dataclass(frozen=True, slots=True)
class PasswordChangeStatus:
    available: bool  # 비밀번호가 있는 계정인지 (Google 로그인만 쓰는 계정은 False)
    state: PasswordChangeState
    expires_at: datetime | None  # 보냄: 링크 만료, 인증: 저장 마감


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalid_link() -> BusinessRuleViolation:
    return BusinessRuleViolation(
        "링크가 만료됐거나 이미 사용됐습니다. 내 정보에서 다시 보내 주세요.",
        code="password_link_invalid",
    )


class PasswordChangeService:
    def __init__(
        self,
        *,
        users: UserRepository,
        store: PasswordChangeStore,
        limiter: RateLimiter,
        hasher: PasswordHasher,
        attempts: LoginAttempts,
        mail: MailSender,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        sender_name: str,
        frontend_base_url: str,
    ) -> None:
        self._users = users
        self._store = store
        self._limiter = limiter
        self._hasher = hasher
        self._attempts = attempts
        self._mail = mail
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._sender_name = sender_name
        self._base_url = frontend_base_url.rstrip("/")

    async def status(self, user_id: uuid.UUID) -> PasswordChangeStatus:
        user = await self._users.get(user_id)
        if user is None or user.hashed_password is None:
            return PasswordChangeStatus(False, PasswordChangeState.NONE, None)
        link = await self._store.get(str(user_id))
        now = self._clock.now()
        state = link.state(now) if link else PasswordChangeState.NONE
        expires = link.expires_at if link and state is not PasswordChangeState.NONE else None
        return PasswordChangeStatus(True, state, expires)

    async def send_link(self, user_id: uuid.UUID) -> PasswordChangeStatus:
        user = await self._password_user(user_id)
        now = self._clock.now()
        key = str(user_id)
        previous = await self._store.get(key)
        if previous is not None and previous.sent_at + LINK_RESEND_INTERVAL > now:
            raise TooManyRequestsError(
                "링크는 1분에 한 번만 보낼 수 있습니다.",
                retry_after=seconds(
                    (previous.sent_at + LINK_RESEND_INTERVAL - now).total_seconds()
                ),
                code="resend_too_soon",
            )
        result = await self._limiter.hit(
            LINK_LIMIT_NAME, key, limit=LINK_DAILY_LIMIT, window_seconds=DAY_SECONDS
        )
        if not result.allowed:
            raise TooManyRequestsError(
                "오늘은 더 보낼 수 없습니다. 내일 다시 시도하세요.",
                retry_after=result.retry_after,
                code="rate_limited",
            )
        if previous is not None:  # 새 링크를 보내면 전 링크는 무효 (A72)
            await self._store.unbind_token(previous.token_hash)
        token = secrets.token_urlsafe(32)
        link = PasswordChangeLink(token_hash=_hash(token), sent_at=now, expires_at=now + LINK_TTL)
        ttl = seconds(LINK_TTL.total_seconds())
        await self._store.put(key, link, ttl_seconds=ttl)
        await self._store.bind_token(link.token_hash, key, ttl_seconds=ttl)
        try:
            await self._mail.send(self._message(user, token))
        except Exception:  # 받지 못한 링크는 남기지 않는다
            await self._store.unbind_token(link.token_hash)
            await self._store.delete(key)
            raise
        return PasswordChangeStatus(True, PasswordChangeState.SENT, link.expires_at)

    async def verify(self, token: str) -> None:
        token_hash = _hash(token)
        user_key = await self._store.user_for_token(token_hash)
        if user_key is None:
            raise _invalid_link()
        link = await self._store.get(user_key)
        now = self._clock.now()
        if (
            link is None
            or link.token_hash != token_hash
            or link.state(now) is not PasswordChangeState.SENT
        ):
            raise _invalid_link()
        verified = link.verified(now)
        await self._store.unbind_token(token_hash)  # 한 번만 쓴다
        await self._store.put(
            user_key, verified, ttl_seconds=seconds((verified.expires_at - now).total_seconds())
        )

    async def change(self, user_id: uuid.UUID, new_password: str) -> None:
        user = await self._password_user(user_id)
        key = str(user_id)
        link = await self._store.get(key)
        if link is None or link.state(self._clock.now()) is not PasswordChangeState.VERIFIED:
            raise BusinessRuleViolation(
                "이메일 인증이 끝나지 않았거나 시간이 지났습니다. 링크를 다시 받아 주세요.",
                code="password_change_not_verified",
            )
        validate_password(new_password)
        hashed = await self._hasher.hash(new_password)
        async with self._uow:
            user.change_password(hashed)
            await self._users.save(user)
            await self._audit.record(
                actor_user_id=user.id,
                action="identity.password.change",
                target_type="user",
                target_id=user.id,
            )
        await self._store.delete(key)
        await self._attempts.clear(user.email)  # A32와 같이 로그인 잠금을 푼다

    async def _password_user(self, user_id: uuid.UUID) -> User:
        user = await self._users.get(user_id)
        if user is None or user.hashed_password is None or user.deleted_at is not None:
            raise BusinessRuleViolation(
                "비밀번호로 로그인하는 계정만 바꿀 수 있습니다.", code="password_not_available"
            )
        return user

    def _message(self, user: User, token: str) -> MailMessage:
        url = f"{self._base_url}{VERIFY_PATH}?token={quote(token)}"
        name = self._sender_name
        return MailMessage(
            to=user.email,
            subject=f"[{name}] 비밀번호 변경 인증",
            text=(
                f"{name} 비밀번호를 바꾸려면 아래 링크를 눌러 인증해 주세요.\n{url}\n"
                "링크는 30분 동안 한 번만 쓸 수 있습니다. 요청하지 않았다면 이 메일을 무시하세요."
            ),
            html=(
                f"<p>{name} 비밀번호를 바꾸려면 아래 버튼을 눌러 인증해 주세요.</p>"
                f'<p><a href="{url}">이메일 인증하기</a></p>'
                "<p>링크는 30분 동안 한 번만 쓸 수 있습니다. "
                "요청하지 않았다면 이 메일을 무시하세요.</p>"
            ),
        )

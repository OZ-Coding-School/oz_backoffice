"""수강생·멘토 이메일 + 비밀번호 로그인과 비밀번호 재설정 (계획 P7, decisions A2·A3·A32).

로그인:
- 실패는 항상 401 `invalid_credentials`(없는 이메일·비밀번호 없는 Google 전용 계정 포함).
- 이메일 기준 15분 안에 5회 실패하면 15분 잠금 → 429 `login_locked` + Retry-After. 잠긴 동안에는
  맞는 비밀번호도 거부한다. 성공하면 실패 횟수를 지운다.
- 승인 대기·반려 회원도 로그인한다(A6, 상태 화면만). 탈퇴·정지 계정은 `account_disabled`.
- 해시 파라미터가 바뀌었으면 로그인할 때 다시 해시한다(B14).

비밀번호 재설정:
- 코드 요청은 항상 204. 비밀번호가 있는 회원(탈퇴 제외)에게만 실제로 보낸다. 그 밖의 이메일도
  코드 기록은 만들어 재발송 간격·발송 제한 응답이 같게 한다.
- 코드 규칙은 가입과 같다(별도 카운터). 재설정하면 로그인 잠금을 풀고, 기존 세션은 유지한다.
"""

import secrets
from typing import Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import LoginResult
from app.contexts.identity.application.tokens import TokenService
from app.contexts.identity.application.verification_codes import VerificationCodes
from app.contexts.identity.domain.credentials import validate_password
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.repositories import UserRepository
from app.contexts.identity.domain.verification import ChallengeKind
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailMessage, MailSender
from app.shared.errors import AuthenticationError, BusinessRuleViolation, TooManyRequestsError
from app.shared.value_objects import Email

RESET_IP_LIMIT = "password_reset_ip"


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...
    async def verify(self, hashed: str, password: str) -> bool: ...
    def needs_rehash(self, hashed: str) -> bool: ...


class LoginAttempts(Protocol):
    async def locked_for(self, email: str) -> int: ...
    async def record_failure(self, email: str) -> int: ...
    async def clear(self, email: str) -> None: ...


def _invalid_credentials() -> AuthenticationError:
    return AuthenticationError(
        "이메일 또는 비밀번호가 올바르지 않습니다.", code="invalid_credentials"
    )


def _locked(seconds: int) -> TooManyRequestsError:
    return TooManyRequestsError(
        "로그인 시도가 많아 잠시 잠겼습니다. 잠시 후 다시 시도하거나 비밀번호를 재설정하세요.",
        retry_after=seconds,
        code="login_locked",
    )


def _normalize(raw: str) -> str | None:
    try:
        return Email(raw).value
    except ValueError:
        return None


class PasswordLoginService:
    def __init__(
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        attempts: LoginAttempts,
        tokens: TokenService,
        uow: UnitOfWork,
        clock: Clock,
        dummy_hash: str,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._attempts = attempts
        self._tokens = tokens
        self._uow = uow
        self._clock = clock
        # 없는 계정도 해시 비교 시간을 들여 응답 시간으로 가입 여부를 알 수 없게 한다
        self._dummy_hash = dummy_hash

    async def login(self, raw_email: str, password: str) -> LoginResult:
        email = _normalize(raw_email)
        if email is None:
            raise _invalid_credentials()
        locked = await self._attempts.locked_for(email)
        if locked:
            raise _locked(locked)
        user = await self._users.get_by_email(email)
        hashed = user.hashed_password if user is not None else None
        valid = await self._hasher.verify(hashed or self._dummy_hash, password)
        if user is None or hashed is None or not valid:
            lock = await self._attempts.record_failure(email)
            if lock:
                raise _locked(lock)
            raise _invalid_credentials()
        await self._attempts.clear(email)
        if not user.can_login:
            raise AuthenticationError(
                "사용할 수 없는 계정입니다. 관리자에게 문의해 주세요.", code="account_disabled"
            )
        async with self._uow:
            if self._hasher.needs_rehash(hashed):
                user.change_password(await self._hasher.hash(password))
            user.record_login(now=self._clock.now())
            await self._users.save(user)
        return LoginResult(user=user, tokens=await self._tokens.issue(user.id))


class PasswordResetService:
    def __init__(
        self,
        *,
        users: UserRepository,
        codes: VerificationCodes,
        hasher: PasswordHasher,
        attempts: LoginAttempts,
        mail: MailSender,
        audit: AuditRecorder,
        uow: UnitOfWork,
        sender_name: str,
    ) -> None:
        self._users = users
        self._codes = codes
        self._hasher = hasher
        self._attempts = attempts
        self._mail = mail
        self._audit = audit
        self._uow = uow
        self._sender_name = sender_name

    async def request_code(self, raw_email: str, *, client_ip: str) -> None:
        email = _normalize(raw_email)
        if email is None:
            raise BusinessRuleViolation("이메일 형식이 올바르지 않습니다.", code="invalid_email")
        kind = ChallengeKind.PASSWORD_RESET
        await self._codes.prepare(
            kind,
            email,
            limit_name="password_reset",
            subject=email,
            ip_limit_name=RESET_IP_LIMIT,
            client_ip=client_ip,
        )
        user = await self._eligible(email)
        code = await self._codes.issue(kind, email, target=email)
        if user is None:
            return  # 보내지 않는다. 기록은 남겨 응답·재발송 동작을 같게 한다
        await self._codes.deliver(
            kind,
            email,
            self._mail.send(
                MailMessage(
                    to=email,
                    subject=f"[{self._sender_name}] 비밀번호 재설정 인증코드 {code}",
                    text=(
                        f"{self._sender_name} 비밀번호 재설정 인증코드는 {code} 입니다.\n"
                        "10분 이내에 입력해 주세요. 요청하지 않았다면 이 메일을 무시하세요."
                    ),
                    html=(
                        f"<p>{self._sender_name} 비밀번호 재설정 인증코드</p>"
                        f'<p style="font-size:24px;font-weight:bold;letter-spacing:4px">{code}</p>'
                        "<p>10분 이내에 입력해 주세요. 요청하지 않았다면 이 메일을 무시하세요.</p>"
                    ),
                )
            ),
        )

    async def reset(self, raw_email: str, code: str, new_password: str) -> None:
        email = _normalize(raw_email)
        if email is None:
            raise BusinessRuleViolation("이메일 형식이 올바르지 않습니다.", code="invalid_email")
        validate_password(new_password)
        await self._codes.verify(ChallengeKind.PASSWORD_RESET, email, code)
        user = await self._eligible(email)
        if user is None:  # 보내지 않은 코드는 맞을 수 없지만, 그사이 탈퇴한 경우를 막는다
            raise BusinessRuleViolation(
                "인증코드가 맞지 않습니다.", code="invalid_verification_code"
            )
        hashed = await self._hasher.hash(new_password)
        async with self._uow:
            user.change_password(hashed)
            await self._users.save(user)
            await self._audit.record(
                actor_user_id=user.id,
                action="identity.password.reset",
                target_type="user",
                target_id=user.id,
            )
        await self._attempts.clear(email)  # 이메일 소유를 확인했으므로 잠금을 푼다 (A32)

    async def _eligible(self, email: str) -> User | None:
        user = await self._users.get_by_email(email)
        if user is None or user.hashed_password is None or user.deleted_at is not None:
            return None
        return user


_dummy_hash: str | None = None


async def dummy_hash(hasher: PasswordHasher) -> str:
    """없는 계정과 비교할 해시. 처음 쓸 때 임의 비밀번호로 한 번 만든다."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = await hasher.hash(secrets.token_urlsafe(16))
    return _dummy_hash

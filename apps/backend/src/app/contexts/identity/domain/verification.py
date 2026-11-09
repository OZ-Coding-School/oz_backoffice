"""인증코드와 가입 세션 (계획 P7, decisions A3·A30).

- 코드: 6자리, 유효 10분, 검증 5회까지, 재발송 간격 60초. 코드는 해시로만 저장한다.
- 가입 세션(가입 토큰): 이메일 인증 후 30분. SMS 인증과 가입 완료가 이 토큰으로 이어진다.
저장소는 Redis(인프라)가 구현한다.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
CODE_MAX_ATTEMPTS = 5
RESEND_INTERVAL = timedelta(seconds=60)
SIGNUP_SESSION_TTL = timedelta(minutes=30)


class ChallengeKind(StrEnum):
    SIGNUP_EMAIL = "signup_email"  # 키: 이메일
    SIGNUP_PHONE = "signup_phone"  # 키: 가입 토큰
    PASSWORD_RESET = "password_reset"  # noqa: S105  # 키: 이메일 (비밀번호 값이 아니라 종류 이름)


@dataclass(frozen=True, slots=True)
class CodeChallenge:
    target: str  # 코드를 보낸 곳 (이메일 또는 휴대폰)
    code_hash: str
    sent_at: datetime
    expires_at: datetime
    attempts: int = 0

    def with_failed_attempt(self) -> "CodeChallenge":
        return replace(self, attempts=self.attempts + 1)


@dataclass(frozen=True, slots=True)
class SignupSession:
    email: str
    email_verified_at: datetime
    expires_at: datetime
    phone_number: str | None = None
    phone_verified_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return self.phone_number is not None and self.phone_verified_at is not None


class ChallengeStore(Protocol):
    async def get(self, kind: ChallengeKind, key: str) -> CodeChallenge | None: ...
    async def put(
        self, kind: ChallengeKind, key: str, challenge: CodeChallenge, *, ttl_seconds: int
    ) -> None: ...
    async def delete(self, kind: ChallengeKind, key: str) -> None: ...


class SignupSessionStore(Protocol):
    async def get(self, token: str) -> SignupSession | None: ...
    async def put(self, token: str, session: SignupSession, *, ttl_seconds: int) -> None: ...
    async def delete(self, token: str) -> None: ...

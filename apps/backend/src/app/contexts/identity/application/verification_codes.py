"""인증코드 발급·검증 공통 규칙 (가입·비밀번호 재설정, decisions A30).

- 6자리, 유효 10분, 검증 5회, 재발송 60초.
- 코드는 HMAC-SHA256 해시로만 저장하고 상수 시간으로 비교한다.
- 발송 제한: 대상당 1시간 5회, IP당 1시간 20회. 재발송 간격을 먼저 검사해 거부된 요청은 세지 않는다.
- 발송에 실패하면 저장한 코드를 지운다(받지 못한 코드는 남기지 않는다).
"""

import hashlib
import hmac
import secrets
from collections.abc import Awaitable
from typing import Protocol

from app.contexts.identity.domain.verification import (
    CODE_LENGTH,
    CODE_MAX_ATTEMPTS,
    CODE_TTL,
    RESEND_INTERVAL,
    ChallengeKind,
    ChallengeStore,
    CodeChallenge,
)
from app.core.clock import Clock
from app.core.rate_limit import RateLimitResult
from app.shared.errors import BusinessRuleViolation, TooManyRequestsError

TARGET_LIMIT = 5  # 대상(이메일·휴대폰)당 1시간
IP_LIMIT = 20  # IP당 1시간
LIMIT_WINDOW_SECONDS = 60 * 60


class RateLimiter(Protocol):
    async def hit(
        self, name: str, subject: str, *, limit: int, window_seconds: int
    ) -> RateLimitResult: ...


def seconds(delta_seconds: float) -> int:
    return max(1, int(delta_seconds))


class VerificationCodes:
    def __init__(
        self, *, challenges: ChallengeStore, limiter: RateLimiter, clock: Clock, secret: str
    ) -> None:
        self._challenges = challenges
        self._limiter = limiter
        self._clock = clock
        self._secret = secret.encode()

    async def prepare(
        self,
        kind: ChallengeKind,
        key: str,
        *,
        limit_name: str,
        subject: str,
        ip_limit_name: str,
        client_ip: str,
    ) -> None:
        """발급 전 검사: 재발송 간격 → 대상당·IP당 제한. 걸리면 429.

        ip_limit_name이 같은 요청끼리 IP 횟수를 합산한다(가입은 메일·SMS 합산).
        """
        await self._ensure_resend_allowed(kind, key)
        for name, limit_subject, limit in (
            (limit_name, subject, TARGET_LIMIT),
            (ip_limit_name, client_ip, IP_LIMIT),
        ):
            result = await self._limiter.hit(
                name, limit_subject, limit=limit, window_seconds=LIMIT_WINDOW_SECONDS
            )
            if not result.allowed:
                raise TooManyRequestsError(
                    "요청이 너무 많습니다. 잠시 후 다시 시도하세요.",
                    retry_after=result.retry_after,
                    code="rate_limited",
                )

    async def issue(self, kind: ChallengeKind, key: str, *, target: str) -> str:
        now = self._clock.now()
        code = f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"
        challenge = CodeChallenge(
            target=target, code_hash=self._hash(code), sent_at=now, expires_at=now + CODE_TTL
        )
        await self._challenges.put(
            kind, key, challenge, ttl_seconds=seconds(CODE_TTL.total_seconds())
        )
        return code

    async def deliver(self, kind: ChallengeKind, key: str, sending: Awaitable[None]) -> None:
        try:
            await sending
        except Exception:
            await self._challenges.delete(kind, key)
            raise

    async def verify(self, kind: ChallengeKind, key: str, code: str) -> CodeChallenge:
        now = self._clock.now()
        challenge = await self._challenges.get(kind, key)
        if challenge is None or challenge.expires_at <= now:
            raise BusinessRuleViolation(
                "인증코드가 만료되었습니다. 다시 받아 주세요.", code="verification_code_expired"
            )
        if challenge.attempts >= CODE_MAX_ATTEMPTS:
            await self._challenges.delete(kind, key)
            raise BusinessRuleViolation(
                "인증 시도 횟수를 넘었습니다. 코드를 다시 받아 주세요.",
                code="verification_attempts_exceeded",
            )
        if not hmac.compare_digest(challenge.code_hash, self._hash(code.strip())):
            failed = challenge.with_failed_attempt()
            if failed.attempts >= CODE_MAX_ATTEMPTS:
                await self._challenges.delete(kind, key)
            else:
                await self._challenges.put(
                    kind,
                    key,
                    failed,
                    ttl_seconds=seconds((challenge.expires_at - now).total_seconds()),
                )
            raise BusinessRuleViolation(
                "인증코드가 맞지 않습니다.", code="invalid_verification_code"
            )
        await self._challenges.delete(kind, key)
        return challenge

    def _hash(self, code: str) -> str:
        return hmac.new(self._secret, code.encode(), hashlib.sha256).hexdigest()

    async def _ensure_resend_allowed(self, kind: ChallengeKind, key: str) -> None:
        now = self._clock.now()
        previous = await self._challenges.get(kind, key)
        if previous is not None and previous.sent_at + RESEND_INTERVAL > now:
            wait = (previous.sent_at + RESEND_INTERVAL - now).total_seconds()
            raise TooManyRequestsError(
                "인증코드는 1분에 한 번만 보낼 수 있습니다.",
                retry_after=seconds(wait),
                code="resend_too_soon",
            )

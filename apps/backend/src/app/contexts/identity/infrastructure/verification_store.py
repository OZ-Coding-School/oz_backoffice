"""인증코드·가입 세션 Redis 저장소.

키: `oz:identity:challenge:<종류>:<키>`, `oz:identity:signup:<토큰>`. 이메일·휴대폰은 키에
그대로 넣지 않고 SHA-256으로 줄여 넣는다(Redis 키 목록에 개인정보가 보이지 않게).
"""

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.contexts.identity.domain.verification import (
    ChallengeKind,
    CodeChallenge,
    SignupSession,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _dump(data: dict[str, Any]) -> str:
    return json.dumps({k: v.isoformat() if isinstance(v, datetime) else v for k, v in data.items()})


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class RedisChallengeStore:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    @staticmethod
    def _key(kind: ChallengeKind, key: str) -> str:
        return f"oz:identity:challenge:{kind.value}:{_digest(key)}"

    async def get(self, kind: ChallengeKind, key: str) -> CodeChallenge | None:
        raw = await self._redis.get(self._key(kind, key))
        if raw is None:
            return None
        data = json.loads(raw)
        return CodeChallenge(
            target=data["target"],
            code_hash=data["code_hash"],
            sent_at=datetime.fromisoformat(data["sent_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            attempts=int(data["attempts"]),
        )

    async def put(
        self, kind: ChallengeKind, key: str, challenge: CodeChallenge, *, ttl_seconds: int
    ) -> None:
        await self._redis.set(self._key(kind, key), _dump(asdict(challenge)), ex=ttl_seconds)

    async def delete(self, kind: ChallengeKind, key: str) -> None:
        await self._redis.delete(self._key(kind, key))


class RedisSignupSessionStore:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    @staticmethod
    def _key(token: str) -> str:
        return f"oz:identity:signup:{_digest(token)}"

    async def get(self, token: str) -> SignupSession | None:
        raw = await self._redis.get(self._key(token))
        if raw is None:
            return None
        data = json.loads(raw)
        return SignupSession(
            email=data["email"],
            email_verified_at=datetime.fromisoformat(data["email_verified_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            phone_number=data.get("phone_number"),
            phone_verified_at=_time(data.get("phone_verified_at")),
        )

    async def put(self, token: str, session: SignupSession, *, ttl_seconds: int) -> None:
        await self._redis.set(self._key(token), _dump(asdict(session)), ex=ttl_seconds)

    async def delete(self, token: str) -> None:
        await self._redis.delete(self._key(token))

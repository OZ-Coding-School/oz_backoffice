"""비밀번호 변경 링크 Redis 저장소 (decisions A72).

키: `oz:identity:pwchange:user:<회원 ID>`(링크 상태),
`oz:identity:pwchange:token:<토큰 해시>`(→ 회원 ID).
토큰 원문은 저장하지 않는다.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING

from app.contexts.identity.domain.password_change import PasswordChangeLink

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisPasswordChangeStore:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"oz:identity:pwchange:user:{user_id}"

    @staticmethod
    def _token_key(token_hash: str) -> str:
        return f"oz:identity:pwchange:token:{token_hash}"

    async def get(self, user_id: str) -> PasswordChangeLink | None:
        raw = await self._redis.get(self._user_key(user_id))
        if raw is None:
            return None
        data = json.loads(raw)
        verified = data.get("verified_at")
        return PasswordChangeLink(
            token_hash=data["token_hash"],
            sent_at=datetime.fromisoformat(data["sent_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            verified_at=datetime.fromisoformat(verified) if verified else None,
        )

    async def put(self, user_id: str, link: PasswordChangeLink, *, ttl_seconds: int) -> None:
        data = {
            "token_hash": link.token_hash,
            "sent_at": link.sent_at.isoformat(),
            "expires_at": link.expires_at.isoformat(),
            "verified_at": link.verified_at.isoformat() if link.verified_at else None,
        }
        await self._redis.set(self._user_key(user_id), json.dumps(data), ex=ttl_seconds)

    async def delete(self, user_id: str) -> None:
        await self._redis.delete(self._user_key(user_id))

    async def user_for_token(self, token_hash: str) -> str | None:
        raw = await self._redis.get(self._token_key(token_hash))
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    async def bind_token(self, token_hash: str, user_id: str, *, ttl_seconds: int) -> None:
        await self._redis.set(self._token_key(token_hash), user_id, ex=ttl_seconds)

    async def unbind_token(self, token_hash: str) -> None:
        await self._redis.delete(self._token_key(token_hash))

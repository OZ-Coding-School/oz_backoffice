"""access / refresh 토큰 발급·회전·폐기 (decisions A7).

- access: 응답 본문으로 주고 `Authorization: Bearer`로 받는다. 저장하지 않는다.
- refresh: HttpOnly 쿠키. jti를 Redis에 저장하고, 갱신할 때마다 새 토큰으로 바꾼다(회전).
  이미 회전·폐기된 refresh가 다시 쓰이면 탈취로 보고 그 사용자의 refresh를 모두 폐기한다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.identity.domain.sessions import RefreshTokenStore
from app.core.clock import Clock
from app.core.security import JWTService
from app.shared.errors import AuthenticationError


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


def _subject_to_user_id(subject: str) -> uuid.UUID:
    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("유효하지 않은 토큰입니다.", code="token_invalid") from exc


def read_access_token(jwt: JWTService, access_token: str) -> uuid.UUID:
    """access 토큰을 검증하고 사용자 ID를 꺼낸다 (저장소 없이 서명·만료만 확인)."""
    return _subject_to_user_id(jwt.decode(access_token, "access").subject)


class TokenService:
    def __init__(self, jwt: JWTService, store: RefreshTokenStore, clock: Clock) -> None:
        self._jwt = jwt
        self._store = store
        self._clock = clock

    async def issue(self, user_id: uuid.UUID) -> IssuedTokens:
        now = self._clock.now()
        access, access_payload = self._jwt.encode(str(user_id), "access", now=now)
        refresh, refresh_payload = self._jwt.encode(str(user_id), "refresh", now=now)
        await self._store.save(refresh_payload.jti, user_id)
        return IssuedTokens(
            access_token=access,
            access_expires_at=access_payload.expires_at,
            refresh_token=refresh,
            refresh_expires_at=refresh_payload.expires_at,
        )

    def read_access(self, access_token: str) -> uuid.UUID:
        return read_access_token(self._jwt, access_token)

    async def consume_refresh(self, refresh_token: str) -> uuid.UUID:
        """refresh를 한 번 쓰고 폐기한다.

        호출한 쪽이 사용자를 확인한 뒤 `issue()`로 새로 발급한다.
        """
        payload = self._jwt.decode(refresh_token, "refresh")
        found = await self._store.consume(payload.jti)
        if found is None:
            raise AuthenticationError(
                "로그인이 만료되었습니다. 다시 로그인해 주세요.", code="refresh_token_revoked"
            )
        if found.reused:
            await self._store.revoke_all(found.user_id)
            raise AuthenticationError(
                "보안을 위해 로그아웃되었습니다. 다시 로그인해 주세요.",
                code="refresh_token_reused",
            )
        return found.user_id

    async def revoke(self, refresh_token: str) -> None:
        """로그아웃. 이미 만료되었거나 잘못된 토큰이면 할 일이 없다."""
        try:
            payload = self._jwt.decode(refresh_token, "refresh")
        except AuthenticationError:
            return
        await self._store.revoke(payload.jti)

    async def revoke_all(self, user_id: uuid.UUID) -> None:
        await self._store.revoke_all(user_id)

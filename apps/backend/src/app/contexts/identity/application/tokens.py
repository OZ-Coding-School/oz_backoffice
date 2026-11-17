"""access / refresh 토큰 발급·회전·폐기 (decisions A7).

- access: 응답 본문으로 주고 `Authorization: Bearer`로 받는다. 저장하지 않는다.
- refresh: HttpOnly 쿠키. jti를 Redis에 저장하고, 갱신할 때마다 새 토큰으로 바꾼다(회전).
  이미 회전·폐기된 refresh가 다시 쓰이면 탈취로 보고 그 사용자의 refresh를 모두 폐기한다.
- 재사용 유예(decisions A60): 회전 직후 `grace_seconds` 안에 같은 refresh가 다시 오면
  (여러 탭의 동시 갱신, 네트워크 재전송) 탈취로 보지 않고 새 access만 발급한다.
  refresh 쿠키는 바꾸지 않으므로 먼저 온 응답이 준 새 refresh가 그대로 쓰인다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contexts.identity.domain.sessions import RefreshLookup, RefreshTokenStore
from app.core.clock import Clock
from app.core.security import JWTService
from app.shared.errors import AuthenticationError


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True, slots=True)
class IssuedAccess:
    """재사용 유예로 access만 새로 발급한 결과 (refresh 쿠키는 그대로 둔다)."""

    access_token: str
    access_expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConsumedRefresh:
    user_id: uuid.UUID
    rotated: bool  # False면 유예 안의 재사용: refresh를 새로 발급하지 않는다


def _subject_to_user_id(subject: str) -> uuid.UUID:
    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise AuthenticationError("유효하지 않은 토큰입니다.", code="token_invalid") from exc


def read_access_token(jwt: JWTService, access_token: str) -> uuid.UUID:
    """access 토큰을 검증하고 사용자 ID를 꺼낸다 (저장소 없이 서명·만료만 확인)."""
    return _subject_to_user_id(jwt.decode(access_token, "access").subject)


class TokenService:
    def __init__(
        self,
        jwt: JWTService,
        store: RefreshTokenStore,
        clock: Clock,
        *,
        reuse_grace_seconds: int = 0,
    ) -> None:
        self._jwt = jwt
        self._store = store
        self._clock = clock
        self._reuse_grace = timedelta(seconds=reuse_grace_seconds)

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

    def issue_access(self, user_id: uuid.UUID) -> IssuedAccess:
        access, payload = self._jwt.encode(str(user_id), "access", now=self._clock.now())
        return IssuedAccess(access_token=access, access_expires_at=payload.expires_at)

    def read_access(self, access_token: str) -> uuid.UUID:
        return read_access_token(self._jwt, access_token)

    async def consume_refresh(self, refresh_token: str) -> ConsumedRefresh:
        """refresh를 한 번 쓰고 폐기한다.

        호출한 쪽이 사용자를 확인한 뒤 `rotated`면 `issue()`로 새로 발급하고,
        유예 안의 재사용이면 `issue_access()`로 access만 발급한다.
        """
        payload = self._jwt.decode(refresh_token, "refresh")
        now = self._clock.now()
        found = await self._store.consume(payload.jti, now=now)
        if found is None:
            raise AuthenticationError(
                "로그인이 만료되었습니다. 다시 로그인해 주세요.", code="refresh_token_revoked"
            )
        if not found.reused:
            return ConsumedRefresh(user_id=found.user_id, rotated=True)
        if self._in_reuse_grace(found, now):
            return ConsumedRefresh(user_id=found.user_id, rotated=False)
        await self._store.revoke_all(found.user_id, now=now)
        raise AuthenticationError(
            "보안을 위해 로그아웃되었습니다. 다시 로그인해 주세요.",
            code="refresh_token_reused",
        )

    def _in_reuse_grace(self, found: RefreshLookup, now: datetime) -> bool:
        """회전(갱신)으로 쓰인 지 유예 시간 안이고, 그 뒤로 로그아웃·전체 폐기가 없었다."""
        if not found.rotated or found.used_at is None:
            return False
        if found.user_revoked_at is not None and found.user_revoked_at >= found.used_at:
            return False
        return now - found.used_at <= self._reuse_grace

    async def revoke(self, refresh_token: str) -> None:
        """로그아웃. 이미 만료되었거나 잘못된 토큰이면 할 일이 없다."""
        try:
            payload = self._jwt.decode(refresh_token, "refresh")
        except AuthenticationError:
            return
        await self._store.revoke(payload.jti, now=self._clock.now())

    async def revoke_all(self, user_id: uuid.UUID) -> None:
        await self._store.revoke_all(user_id, now=self._clock.now())

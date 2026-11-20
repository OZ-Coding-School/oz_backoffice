"""내 정보 비밀번호 변경 링크 (decisions A72).

- 로그인한 회원이 요청하면 내 이메일로 인증 링크를 보낸다. 링크는 30분 유효·한 번만 쓴다.
- 링크를 누르면 인증되고, 그 뒤 10분 안에 새 비밀번호를 저장한다.
- 다시 보내기는 1분 간격·하루 5회. 새 링크를 보내면 전 링크는 무효다.
저장소는 Redis(인프라)가 구현한다.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

LINK_TTL = timedelta(minutes=30)
CHANGE_WINDOW = timedelta(minutes=10)
LINK_RESEND_INTERVAL = timedelta(seconds=60)
LINK_DAILY_LIMIT = 5


class PasswordChangeState(StrEnum):
    NONE = "NONE"  # 보낸 링크가 없거나 만료됨
    SENT = "SENT"  # 링크를 보냈고 아직 누르지 않음
    VERIFIED = "VERIFIED"  # 링크를 눌러 새 비밀번호를 저장할 수 있음


@dataclass(frozen=True, slots=True)
class PasswordChangeLink:
    token_hash: str
    sent_at: datetime
    expires_at: datetime  # 보냄: 링크 만료, 인증 후: 저장 마감
    verified_at: datetime | None = None

    def state(self, now: datetime) -> PasswordChangeState:
        if self.expires_at <= now:
            return PasswordChangeState.NONE
        return PasswordChangeState.VERIFIED if self.verified_at else PasswordChangeState.SENT

    def verified(self, now: datetime) -> "PasswordChangeLink":
        return replace(self, verified_at=now, expires_at=now + CHANGE_WINDOW)


class PasswordChangeStore(Protocol):
    async def get(self, user_id: str) -> PasswordChangeLink | None: ...
    async def put(self, user_id: str, link: PasswordChangeLink, *, ttl_seconds: int) -> None: ...
    async def delete(self, user_id: str) -> None: ...
    async def user_for_token(self, token_hash: str) -> str | None: ...
    async def bind_token(self, token_hash: str, user_id: str, *, ttl_seconds: int) -> None: ...
    async def unbind_token(self, token_hash: str) -> None: ...

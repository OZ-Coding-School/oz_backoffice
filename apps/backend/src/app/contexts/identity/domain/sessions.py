"""로그인 세션 저장소 인터페이스 (refresh 토큰, OAuth state)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RefreshLookup:
    user_id: uuid.UUID
    reused: bool  # 이미 회전·폐기된 토큰이 다시 쓰였다 (탈취 의심, 유예 판정 전)
    # 아래는 reused=True일 때만 의미가 있다 (재사용 유예 판정, decisions A60)
    used_at: datetime | None = None  # 회전·폐기된 시각
    rotated: bool = False  # 갱신(회전)으로 쓰였다 (로그아웃·전체 폐기가 아님)
    user_revoked_at: datetime | None = None  # 그 사용자의 마지막 로그아웃·전체 폐기 시각


class RefreshTokenStore(Protocol):
    async def save(self, jti: str, user_id: uuid.UUID) -> None: ...

    async def consume(self, jti: str, *, now: datetime) -> RefreshLookup | None:
        """활성 토큰이면 지우고(회전, 사용 시각 기록) 반환한다.

        이미 쓰인 토큰이면 reused=True와 사용 시각, 모르는 토큰이면 None.
        """
        ...

    async def revoke(self, jti: str, *, now: datetime) -> None:
        """로그아웃. 그 사용자의 재사용 유예도 끝낸다."""
        ...

    async def revoke_all(self, user_id: uuid.UUID, *, now: datetime) -> None:
        """전체 폐기. 그 사용자의 재사용 유예도 끝낸다."""
        ...


class OAuthStateStore(Protocol):
    async def save(self, state: str, code_verifier: str) -> None: ...

    async def pop(self, state: str) -> str | None:
        """state에 묶인 PKCE verifier를 꺼내고 지운다 (한 번만 쓸 수 있다)."""
        ...

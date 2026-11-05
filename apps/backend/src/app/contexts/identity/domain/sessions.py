"""로그인 세션 저장소 인터페이스 (refresh 토큰, OAuth state)."""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RefreshLookup:
    user_id: uuid.UUID
    reused: bool  # 이미 회전·폐기된 토큰이 다시 쓰였다 (탈취 의심)


class RefreshTokenStore(Protocol):
    async def save(self, jti: str, user_id: uuid.UUID) -> None: ...

    async def consume(self, jti: str) -> RefreshLookup | None:
        """활성 토큰이면 지우고(회전) 반환한다.

        이미 쓰인 토큰이면 reused=True, 모르는 토큰이면 None.
        """
        ...

    async def revoke(self, jti: str) -> None: ...

    async def revoke_all(self, user_id: uuid.UUID) -> None: ...


class OAuthStateStore(Protocol):
    async def save(self, state: str, code_verifier: str) -> None: ...

    async def pop(self, state: str) -> str | None:
        """state에 묶인 PKCE verifier를 꺼내고 지운다 (한 번만 쓸 수 있다)."""
        ...

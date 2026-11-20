"""녹화 파일 서명 링크 (decisions A68, BE-2b).

`<video src>`·내려받기는 Authorization 헤더를 보낼 수 없어, 참여자가 요청하면 그 파일·그 사용자에
묶인 짧은 서명 토큰(3시간)을 붙인 링크를 준다. 링크로 받을 때도 매번 참여자인지 다시 확인한다.
토큰 종류(`typ`)가 달라 access 토큰으로는 쓸 수 없고, 서명 토큰도 다른 API에는 쓸 수 없다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from app.core.config import Settings
from app.shared.errors import AuthenticationError

LINK_TTL = timedelta(hours=3)
TOKEN_TYPE = "artifact"  # noqa: S105 - 토큰 종류 이름이지 비밀 값이 아니다


@dataclass(frozen=True, slots=True)
class ArtifactGrant:
    user_id: uuid.UUID
    session_id: uuid.UUID
    artifact_id: uuid.UUID


def _invalid() -> AuthenticationError:
    return AuthenticationError("링크가 만료됐거나 올바르지 않습니다.", code="artifact_link_invalid")


class ArtifactLinkSigner:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret_key.get_secret_value()
        self._algorithm = settings.jwt_algorithm

    def sign(self, grant: ArtifactGrant, *, now: datetime) -> tuple[str, datetime]:
        expires_at = now + LINK_TTL
        token = jwt.encode(
            {
                "typ": TOKEN_TYPE,
                "sub": str(grant.user_id),
                "sid": str(grant.session_id),
                "aid": str(grant.artifact_id),
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
            },
            self._secret,
            algorithm=self._algorithm,
        )
        return token, expires_at

    def verify(self, token: str, artifact_id: uuid.UUID) -> ArtifactGrant:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["typ", "sub", "sid", "aid", "exp"]},
            )
            grant = ArtifactGrant(
                user_id=uuid.UUID(claims["sub"]),
                session_id=uuid.UUID(claims["sid"]),
                artifact_id=uuid.UUID(claims["aid"]),
            )
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise _invalid() from exc
        if claims["typ"] != TOKEN_TYPE or grant.artifact_id != artifact_id:
            raise _invalid()
        return grant

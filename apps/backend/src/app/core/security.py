"""JWT 발급/검증과 비밀번호 해시."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import Settings
from app.shared.errors import AuthenticationError

TokenType = Literal["access", "refresh"]

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(hashed, password)
    except VerificationError:
        return False


@dataclass(frozen=True, slots=True)
class TokenPayload:
    subject: str
    token_type: TokenType
    jti: str
    issued_at: datetime
    expires_at: datetime


class JWTService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret_key.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._ttl: dict[TokenType, int] = {
            "access": settings.access_token_ttl_seconds,
            "refresh": settings.refresh_token_ttl_seconds,
        }

    def encode(
        self, subject: str, token_type: TokenType, *, now: datetime
    ) -> tuple[str, TokenPayload]:
        payload = TokenPayload(
            subject=subject,
            token_type=token_type,
            jti=uuid.uuid4().hex,
            issued_at=now,
            expires_at=now + timedelta(seconds=self._ttl[token_type]),
        )
        claims: dict[str, Any] = {
            "sub": payload.subject,
            "typ": payload.token_type,
            "jti": payload.jti,
            "iat": int(payload.issued_at.timestamp()),
            "exp": int(payload.expires_at.timestamp()),
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm), payload

    def decode(self, token: str, expected_type: TokenType) -> TokenPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["sub", "typ", "jti", "iat", "exp"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("토큰이 만료되었습니다.", code="token_expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("유효하지 않은 토큰입니다.", code="token_invalid") from exc
        if claims["typ"] != expected_type:
            raise AuthenticationError("토큰 유형이 올바르지 않습니다.", code="token_invalid")
        return TokenPayload(
            subject=claims["sub"],
            token_type=claims["typ"],
            jti=claims["jti"],
            issued_at=datetime.fromtimestamp(claims["iat"]).astimezone(),
            expires_at=datetime.fromtimestamp(claims["exp"]).astimezone(),
        )

"""운영진 Google 로그인 어댑터 (OAuth 2.0 Authorization Code + PKCE, OpenID Connect).

ID 토큰은 토큰 엔드포인트에서 client secret으로 인증한 HTTPS 응답으로 직접 받는다.
그래서 서명(JWKS)은 검증하지 않고 클레임(aud, iss, exp, hd, email_verified)만 검증한다.
Google 문서가 허용하는 방식이며, RS256 검증용 cryptography 의존성을 추가하지 않기 위해 택했다
(decisions A12).
"""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.shared.errors import AuthenticationError

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL이지 비밀번호가 아니다
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
SCOPES = "openid email profile"
_CLOCK_SKEW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    subject: str
    email: str
    name: str | None
    hosted_domain: str | None


@dataclass(frozen=True, slots=True)
class PkcePair:
    verifier: str
    challenge: str


def new_pkce_pair() -> PkcePair:
    verifier = secrets.token_urlsafe(64)  # 86자 (RFC 7636: 43~128자)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(verifier=verifier, challenge=challenge)


def _fail(message: str = "Google 인증에 실패했습니다.") -> AuthenticationError:
    return AuthenticationError(message, code="google_auth_failed")


class GoogleOAuthClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        hosted_domain: str,
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._hosted_domain = hosted_domain.lower()

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "hd": self._hosted_domain,  # 계정 선택 화면 힌트일 뿐이라 콜백에서 다시 검증한다
            "prompt": "select_account",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> GoogleIdentity:
        try:
            response = await self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "code_verifier": code_verifier,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "redirect_uri": self._redirect_uri,
                },
            )
        except httpx.HTTPError as exc:
            raise _fail() from exc
        if response.status_code != httpx.codes.OK:
            raise _fail()
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise _fail()
        return self.parse_id_token(id_token)

    def parse_id_token(self, id_token: str, *, now: float | None = None) -> GoogleIdentity:
        try:
            claims: dict[str, Any] = jwt.decode(id_token, options={"verify_signature": False})
        except jwt.InvalidTokenError as exc:
            raise _fail() from exc

        current = time.time() if now is None else now
        if claims.get("aud") != self._client_id or claims.get("iss") not in ISSUERS:
            raise _fail()
        expires_at = claims.get("exp")
        if not isinstance(expires_at, int) or expires_at + _CLOCK_SKEW_SECONDS < current:
            raise _fail()

        subject, email = claims.get("sub"), claims.get("email")
        if not isinstance(subject, str) or not isinstance(email, str):
            raise _fail()
        if claims.get("email_verified") is not True:
            raise _fail("Google 계정 이메일이 인증되지 않았습니다.")
        hosted_domain = claims.get("hd")
        email = email.strip().lower()
        if hosted_domain != self._hosted_domain or not email.endswith(f"@{self._hosted_domain}"):
            raise AuthenticationError(
                f"{self._hosted_domain} 계정으로만 로그인할 수 있습니다.",
                code="google_domain_not_allowed",
            )
        name = claims.get("name")
        return GoogleIdentity(
            subject=subject,
            email=email,
            name=name if isinstance(name, str) and name.strip() else None,
            hosted_domain=hosted_domain,
        )

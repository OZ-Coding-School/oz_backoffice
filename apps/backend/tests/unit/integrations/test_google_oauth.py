import base64
import hashlib
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
import respx

from app.integrations.google.oauth import TOKEN_URL, GoogleOAuthClient, new_pkce_pair
from app.shared.errors import AuthenticationError

pytestmark = pytest.mark.unit

CLIENT_ID = "client-id.apps.googleusercontent.com"


def id_token(**overrides: Any) -> str:
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "Kim@NextRunners.co.kr",
        "email_verified": True,
        "hd": "nextrunners.co.kr",
        "name": "김오즈",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, "unused-signing-key-for-tests-0123456789", algorithm="HS256")


@pytest.fixture
async def google() -> Any:
    async with httpx.AsyncClient() as http:
        yield GoogleOAuthClient(
            http,
            client_id=CLIENT_ID,
            client_secret="secret",
            redirect_uri="http://localhost:5173/auth/google/callback",
            hosted_domain="nextrunners.co.kr",
        )


def test_pkce_challenge_is_s256_of_verifier() -> None:
    pair = new_pkce_pair()
    assert 43 <= len(pair.verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(pair.verifier.encode()).digest())
    assert pair.challenge == expected.rstrip(b"=").decode()


def test_authorization_url_has_state_pkce_and_domain_hint(google: GoogleOAuthClient) -> None:
    url = google.authorization_url(state="st", code_challenge="ch")
    query = parse_qs(urlparse(url).query)
    assert query["state"] == ["st"]
    assert query["code_challenge"] == ["ch"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["hd"] == ["nextrunners.co.kr"]
    assert query["scope"] == ["openid email profile"]


@respx.mock
async def test_exchange_code_returns_normalized_identity(google: GoogleOAuthClient) -> None:
    route = respx.post(TOKEN_URL).respond(200, json={"id_token": id_token()})

    identity = await google.exchange_code(code="auth-code", code_verifier="verifier")

    assert (identity.subject, identity.email, identity.name) == (
        "1234567890",
        "kim@nextrunners.co.kr",
        "김오즈",
    )
    body = parse_qs(route.calls.last.request.content.decode())
    assert body["code_verifier"] == ["verifier"]
    assert body["grant_type"] == ["authorization_code"]


@respx.mock
@pytest.mark.parametrize(
    "response",
    [httpx.Response(400, json={"error": "invalid_grant"}), httpx.Response(200, json={})],
)
async def test_exchange_code_failure(google: GoogleOAuthClient, response: httpx.Response) -> None:
    respx.post(TOKEN_URL).mock(return_value=response)
    with pytest.raises(AuthenticationError) as exc:
        await google.exchange_code(code="bad", code_verifier="v")
    assert exc.value.code == "google_auth_failed"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"aud": "other-client"}, "google_auth_failed"),
        ({"iss": "https://evil.example.com"}, "google_auth_failed"),
        ({"exp": int(time.time()) - 3600}, "google_auth_failed"),
        ({"email_verified": False}, "google_auth_failed"),
        ({"hd": None, "email": "kim@gmail.com"}, "google_domain_not_allowed"),
        ({"hd": "other.co.kr"}, "google_domain_not_allowed"),
        ({"email": "kim@gmail.com"}, "google_domain_not_allowed"),
    ],
)
def test_id_token_claims_are_validated(
    google: GoogleOAuthClient, overrides: dict[str, Any], code: str
) -> None:
    with pytest.raises(AuthenticationError) as exc:
        google.parse_id_token(id_token(**overrides))
    assert exc.value.code == code

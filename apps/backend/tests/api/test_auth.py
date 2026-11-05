from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import parse_qs, urlparse

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import Depends, FastAPI
from httpx import AsyncClient, Response

from app.contexts.access.presentation.dependencies import ApprovedUser
from app.contexts.identity.application.auth_service import (
    SessionService,
    StaffGoogleLoginService,
    UserQueries,
)
from app.contexts.identity.application.tokens import TokenService
from app.contexts.identity.infrastructure.token_store import RedisOAuthStateStore
from app.contexts.identity.presentation.dependencies import (
    get_session_service,
    get_staff_login_service,
    get_token_service,
)
from app.core.clock import FixedClock
from app.integrations.google.oauth import GoogleIdentity
from tests.fakes.identity import FakeGoogleAuthenticator, InMemoryUserRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.api

STAFF = GoogleIdentity(
    subject="google-sub-1", email="kim@nextrunners.co.kr", name="김오즈", hosted_domain="x"
)


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def auth_app(app: FastAPI, users: InMemoryUserRepository, fake_redis: FakeAsyncRedis) -> FastAPI:
    clock = FixedClock(datetime.now(UTC))
    google = FakeGoogleAuthenticator()
    google.identities["good-code"] = STAFF
    app.state.clock = clock
    app.state.user_queries = UserQueries(users)

    def login_service(
        tokens: Annotated[TokenService, Depends(get_token_service)],
    ) -> StaffGoogleLoginService:
        return StaffGoogleLoginService(
            google=google,
            states=RedisOAuthStateStore(fake_redis),
            users=users,
            tokens=tokens,
            uow=FakeUnitOfWork(),
            clock=clock,
        )

    def session_service(
        tokens: Annotated[TokenService, Depends(get_token_service)],
    ) -> SessionService:
        return SessionService(users=users, tokens=tokens)

    app.dependency_overrides[get_staff_login_service] = login_service
    app.dependency_overrides[get_session_service] = session_service

    @app.get("/_test/approved-only")
    async def approved_only(user: ApprovedUser) -> dict[str, str]:
        return {"email": user.email}

    return app


@pytest.fixture
async def auth_client(auth_app: FastAPI, client: AsyncClient) -> AsyncClient:
    return client


async def login(client: AsyncClient) -> Response:
    authorize = await client.get("/api/v1/auth/google/authorize")
    assert authorize.status_code == 200
    state = parse_qs(urlparse(authorize.json()["authorization_url"]).query)["state"][0]
    return await client.post(
        "/api/v1/auth/google/callback", json={"code": "good-code", "state": state}
    )


def refresh_cookie(response: Response) -> str:
    header = response.headers["set-cookie"]
    return header.split(";", 1)[0].split("=", 1)[1]


def bearer(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_google_login_sets_refresh_cookie(auth_client: AsyncClient) -> None:
    response = await login(auth_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    cookie = response.headers["set-cookie"].lower()
    for attribute in ("oz_refresh=", "httponly", "secure", "samesite=lax", "path=/api/v1/auth"):
        assert attribute in cookie
    assert response.headers["cache-control"] == "no-store"


async def test_callback_rejects_unknown_state(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/google/callback", json={"code": "good-code", "state": "forged"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_state_invalid"


async def test_me_shows_pending_status_and_gate_blocks(auth_client: AsyncClient) -> None:
    logged_in = await login(auth_client)

    me = await auth_client.get("/api/v1/me", headers=bearer(logged_in))
    assert me.status_code == 200
    assert me.json()["email"] == "kim@nextrunners.co.kr"
    assert me.json()["approval_status"] == "PENDING"

    gated = await auth_client.get("/_test/approved-only", headers=bearer(logged_in))
    assert gated.status_code == 403
    assert gated.json()["error"]["code"] == "approval_required"


async def test_approved_user_passes_gate(
    auth_client: AsyncClient, users: InMemoryUserRepository
) -> None:
    logged_in = await login(auth_client)
    user = next(iter(users.users.values()))
    user.approve(now=datetime.now(UTC))
    await users.save(user)

    response = await auth_client.get("/_test/approved-only", headers=bearer(logged_in))
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({}, "unauthenticated"),
        ({"Authorization": "Bearer not-a-jwt"}, "token_invalid"),
    ],
)
async def test_me_requires_valid_access_token(
    auth_client: AsyncClient, headers: dict[str, str], code: str
) -> None:
    response = await auth_client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code


async def test_refresh_rotates_cookie_and_detects_reuse(auth_client: AsyncClient) -> None:
    first = refresh_cookie(await login(auth_client))

    renewed = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={first}"}
    )
    assert renewed.status_code == 200
    second = refresh_cookie(renewed)
    assert second != first

    reused = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={first}"}
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "refresh_token_reused"
    # 재사용이 탐지되면 새로 받은 refresh도 폐기된다
    revoked = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={second}"}
    )
    assert revoked.status_code == 401


async def test_refresh_without_cookie(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_token_missing"


async def test_logout_clears_cookie_and_revokes(auth_client: AsyncClient) -> None:
    cookie = refresh_cookie(await login(auth_client))

    response = await auth_client.post(
        "/api/v1/auth/logout", headers={"Cookie": f"oz_refresh={cookie}"}
    )
    assert response.status_code == 204
    assert 'oz_refresh=""' in response.headers["set-cookie"]

    after = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={cookie}"}
    )
    assert after.status_code == 401


async def test_google_login_not_configured(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/google/authorize")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "google_login_not_configured"

from datetime import UTC, datetime, timedelta
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
def auth_app(
    app: FastAPI,
    users: InMemoryUserRepository,
    fake_redis: FakeAsyncRedis,
) -> FastAPI:
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


def set_cookie(response: Response, name: str) -> str:
    """응답의 Set-Cookie 중 name 쿠키의 전체 헤더 값."""
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}="))


def cookie_value(response: Response, name: str) -> str:
    return set_cookie(response, name).split(";", 1)[0].split("=", 1)[1]


def refresh_cookie(response: Response) -> str:
    return cookie_value(response, "oz_refresh")


async def google_redirect(client: AsyncClient) -> tuple[str, str]:
    """/google/login → (Google로 보낸 state, 브라우저에 내려준 state 쿠키)."""
    start = await client.get("/api/v1/auth/google/login")
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    return state, cookie_value(start, "oz_oauth_state")


async def callback(
    client: AsyncClient, *, state: str, state_cookie: str | None, **params: str
) -> Response:
    headers = {"Cookie": f"oz_oauth_state={state_cookie}"} if state_cookie else {}
    return await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "good-code", "state": state, **params},
        headers=headers,
    )


async def login(client: AsyncClient) -> Response:
    """Google 로그인 → 프론트로 리디렉션 → /auth/refresh로 access 토큰을 받는 전체 흐름."""
    state, state_cookie = await google_redirect(client)
    done = await callback(client, state=state, state_cookie=state_cookie)
    assert done.status_code == 302
    assert done.headers["location"] == "http://localhost:5173/"
    return await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={refresh_cookie(done)}"}
    )


def bearer(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_google_login_redirects_with_state_cookie(auth_client: AsyncClient) -> None:
    start = await auth_client.get("/api/v1/auth/google/login")

    assert start.status_code == 302
    assert start.headers["location"].startswith("https://accounts.google.test/auth?")
    cookie = set_cookie(start, "oz_oauth_state").lower()
    for attribute in (
        "httponly",
        "secure",
        "samesite=lax",
        "path=/api/v1/auth/google",
        "max-age=600",
    ):
        assert attribute in cookie


async def test_callback_sets_refresh_cookie_and_redirects(auth_client: AsyncClient) -> None:
    state, state_cookie = await google_redirect(auth_client)

    done = await callback(auth_client, state=state, state_cookie=state_cookie)

    assert done.status_code == 302
    assert done.headers["location"] == "http://localhost:5173/"
    cookie = set_cookie(done, "oz_refresh").lower()
    for attribute in ("httponly", "secure", "samesite=lax", "path=/api/v1/auth"):
        assert attribute in cookie
    assert 'oz_oauth_state=""' in set_cookie(done, "oz_oauth_state")  # state 쿠키 삭제

    tokens = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={refresh_cookie(done)}"}
    )
    assert tokens.status_code == 200
    assert tokens.json()["token_type"] == "bearer"
    assert tokens.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("use_cookie", "params", "code"),
    [
        (False, {}, "oauth_state_invalid"),  # 다른 브라우저 (로그인 CSRF)
        (True, {"error": "access_denied"}, "google_login_cancelled"),
        (True, {"code": "bad-code"}, "google_auth_failed"),
    ],
)
async def test_callback_failure_redirects_to_login_page(
    auth_client: AsyncClient, use_cookie: bool, params: dict[str, str], code: str
) -> None:
    state, state_cookie = await google_redirect(auth_client)

    done = await callback(
        auth_client, state=state, state_cookie=state_cookie if use_cookie else None, **params
    )

    assert done.status_code == 302
    assert done.headers["location"] == f"http://localhost:5173/staff/login?error={code}"
    assert not any(h.startswith("oz_refresh=") for h in done.headers.get_list("set-cookie"))


async def test_callback_with_forged_state_cookie(auth_client: AsyncClient) -> None:
    await google_redirect(auth_client)
    done = await callback(auth_client, state="forged", state_cookie="forged")
    assert done.headers["location"] == "http://localhost:5173/staff/login?error=oauth_state_invalid"


async def test_me_shows_pending_status_and_gate_blocks(auth_client: AsyncClient) -> None:
    logged_in = await login(auth_client)

    me = await auth_client.get("/api/v1/me", headers=bearer(logged_in))
    assert me.status_code == 200
    assert me.json()["email"] == "kim@nextrunners.co.kr"
    assert me.json()["approval_status"] == "PENDING"
    assert me.json()["account_type"] == "STAFF"  # Google 로그인으로 만든 계정 (A61)
    assert me.json()["is_super_admin"] is False

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


async def test_refresh_reuse_within_grace_keeps_cookie(auth_client: AsyncClient) -> None:
    """회전 직후 같은 refresh가 다시 오면 access만 주고 쿠키는 바꾸지 않는다 (A60)."""
    first = refresh_cookie(await login(auth_client))
    renewed = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={first}"}
    )
    second = refresh_cookie(renewed)

    again = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={first}"}
    )
    assert again.status_code == 200
    assert again.json()["access_token"]
    assert again.headers["cache-control"] == "no-store"
    assert not any(h.startswith("oz_refresh=") for h in again.headers.get_list("set-cookie"))
    # 먼저 받은 새 refresh는 그대로 쓸 수 있다
    still = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={second}"}
    )
    assert still.status_code == 200


async def test_refresh_rotates_cookie_and_detects_reuse(
    auth_app: FastAPI, auth_client: AsyncClient
) -> None:
    first = refresh_cookie(await login(auth_client))

    renewed = await auth_client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"oz_refresh={first}"}
    )
    assert renewed.status_code == 200
    second = refresh_cookie(renewed)
    assert second != first

    clock = auth_app.state.clock
    clock.set(clock.now() + timedelta(seconds=11))  # 유예 시간(10초)이 지난 재사용
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
    response = await client.get("/api/v1/auth/google/login")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "google_login_not_configured"


async def test_me_shows_super_admin(
    auth_client: AsyncClient, users: InMemoryUserRepository
) -> None:
    logged_in = await login(auth_client)
    user = next(iter(users.users.values()))
    user.approve(now=datetime.now(UTC))
    user.set_super_admin(True)

    me = await auth_client.get("/api/v1/me", headers=bearer(logged_in))

    assert me.json()["is_super_admin"] is True

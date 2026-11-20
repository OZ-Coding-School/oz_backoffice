"""이메일 + 비밀번호 로그인과 비밀번호 재설정 API (실제 DB, fakeredis, 메모리 발송)."""

import re
from urllib.parse import unquote

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contexts.identity.infrastructure.passwords import Argon2PasswordHasher
from tests.factories.educator import create_user
from tests.fakes.notifications import InMemoryMailSender

pytestmark = pytest.mark.api

AUTH = "/api/v1/auth"
EMAIL = "kim@gmail.com"


@pytest.fixture
def mail(app: FastAPI) -> InMemoryMailSender:
    sender = InMemoryMailSender()
    app.state.mail_sender = sender
    return sender


PASSWORD = "abcd123!"  # 테스트용 비밀번호


async def _member() -> None:
    await create_user(email=EMAIL, hashed_password=await Argon2PasswordHasher().hash(PASSWORD))


async def _login(client: AsyncClient, password: str) -> int:
    response = await client.post(f"{AUTH}/login", json={"email": EMAIL, "password": password})
    return response.status_code


async def test_login_sets_refresh_cookie_and_me_works(client: AsyncClient) -> None:
    await _member()
    response = await client.post(f"{AUTH}/login", json={"email": EMAIL, "password": "abcd123!"})

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert any(h.startswith("oz_refresh=") for h in response.headers.get_list("set-cookie"))
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["approval_status"] == "PENDING"  # 승인 대기도 로그인한다 (A6)


async def test_lockout_and_reset_unlock(client: AsyncClient, mail: InMemoryMailSender) -> None:
    await _member()
    assert [await _login(client, "wrong123!") for _ in range(5)] == [401, 401, 401, 401, 429]
    locked = await client.post(f"{AUTH}/login", json={"email": EMAIL, "password": "abcd123!"})
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "login_locked"
    assert int(locked.headers["retry-after"]) > 800

    sent = await client.post(f"{AUTH}/password-reset/code", json={"email": EMAIL})
    assert sent.status_code == 204
    match = re.search(r"\b(\d{6})\b", mail.sent[-1].text)
    assert match
    reset = await client.post(
        f"{AUTH}/password-reset",
        json={"email": EMAIL, "code": match.group(1), "new_password": "newpass1!"},
    )
    assert reset.status_code == 204, reset.text

    assert await _login(client, "newpass1!") == 200
    assert await _login(client, "abcd123!") == 401


async def test_reset_code_does_not_reveal_accounts(
    client: AsyncClient, mail: InMemoryMailSender
) -> None:
    response = await client.post(f"{AUTH}/password-reset/code", json={"email": "nobody@gmail.com"})
    assert response.status_code == 204
    assert mail.sent == []


async def test_unknown_email_gets_same_error(client: AsyncClient) -> None:
    response = await client.post(
        f"{AUTH}/login", json={"email": "nobody@gmail.com", "password": "abcd123!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_my_password_change_by_link(client: AsyncClient, mail: InMemoryMailSender) -> None:
    """내 정보 비밀번호 변경: 링크 → 인증 → 저장 (A72)."""
    await _member()
    token = (
        await client.post(f"{AUTH}/login", json={"email": EMAIL, "password": PASSWORD})
    ).json()["access_token"]
    me = {"Authorization": f"Bearer {token}"}
    base = "/api/v1/me/password-change"

    status = (await client.get(base, headers=me)).json()
    assert (status["available"], status["state"]) == (True, "NONE")
    sent = await client.post(f"{base}/link", headers=me)
    assert sent.status_code == 200, sent.text
    assert sent.json()["state"] == "SENT"
    assert (await client.post(f"{base}/link", headers=me)).status_code == 429
    early = await client.post(base, headers=me, json={"new_password": "newpass1!"})
    assert early.json()["error"]["code"] == "password_change_not_verified"

    match = re.search(r"token=(\S+)", mail.sent[-1].text)
    assert match
    link_token = unquote(match.group(1))
    verified = await client.post(f"{AUTH}/password-change/verify", json={"token": link_token})
    assert verified.status_code == 204, verified.text
    again = await client.post(f"{AUTH}/password-change/verify", json={"token": link_token})
    assert again.json()["error"]["code"] == "password_link_invalid"
    assert (await client.get(base, headers=me)).json()["state"] == "VERIFIED"

    changed = await client.post(base, headers=me, json={"new_password": "newpass1!"})
    assert changed.status_code == 204, changed.text
    assert await _login(client, "newpass1!") == 200
    assert await _login(client, PASSWORD) == 401
    assert (await client.get("/api/v1/me", headers=me)).status_code == 200  # 세션은 유지 (A32)
    assert (await client.get(base)).status_code == 401

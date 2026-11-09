"""수강생·멘토 가입 API (실제 DB, fakeredis, 메모리 발송 드라이버)."""

import re
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.infrastructure.models import CohortModel
from app.contexts.identity.infrastructure.models import MemberSignupModel, UserModel
from app.core.config import Settings
from tests.factories.academy import create_cohort
from tests.factories.educator import create_user
from tests.fakes.notifications import InMemoryMailSender, InMemorySmsSender

pytestmark = pytest.mark.api

API = "/api/v1/auth/signup"
EMAIL = "kim@gmail.com"


@pytest.fixture
def senders(app: FastAPI) -> tuple[InMemoryMailSender, InMemorySmsSender]:
    mail, sms = InMemoryMailSender(), InMemorySmsSender()
    app.state.mail_sender = mail
    app.state.sms_sender = sms
    return mail, sms


def _code(text: str) -> str:
    match = re.search(r"\b(\d{6})\b", text)
    assert match
    return match.group(1)


async def _verified_token(
    client: AsyncClient, senders: tuple[InMemoryMailSender, InMemorySmsSender]
) -> str:
    mail, sms = senders
    sent = await client.post(f"{API}/email-code", json={"email": "Kim@Gmail.com"})
    assert sent.status_code == 204, sent.text
    verified = await client.post(
        f"{API}/email-code/verify", json={"email": EMAIL, "code": _code(mail.sent[-1].text)}
    )
    assert verified.status_code == 200, verified.text
    token: str = verified.json()["signup_token"]
    assert verified.json()["expires_in"] == 1800
    phone = await client.post(
        f"{API}/phone-code", json={"signup_token": token, "phone_number": "010-1234-5678"}
    )
    assert phone.status_code == 204, phone.text
    phone_ok = await client.post(
        f"{API}/phone-code/verify", json={"signup_token": token, "code": _code(sms.sent[-1].text)}
    )
    assert phone_ok.status_code == 204, phone_ok.text
    return token


async def test_student_signup_flow(
    client: AsyncClient, senders: tuple[InMemoryMailSender, InMemorySmsSender]
) -> None:
    cohort = await create_cohort()
    token = await _verified_token(client, senders)

    body: dict[str, Any] = {
        "signup_token": token,
        "name": "김수강",
        "password": "abcd123!",
        "signup_type": "STUDENT",
        "cohort_id": str(cohort.id),
    }
    response = await client.post(API, json=body)

    assert response.status_code == 201, response.text
    assert response.json()["approval_status"] == "PENDING"
    user = await UserModel.get(id=response.json()["user_id"])
    assert (user.email, user.phone_number) == (EMAIL, "01012345678")
    assert user.hashed_password is not None
    assert user.hashed_password.startswith("$argon2id$")
    signup = await MemberSignupModel.get(id=response.json()["signup_id"])
    assert signup.requested_cohort_id == cohort.id  # type: ignore[attr-defined]  # FK 컬럼 속성
    assert "access_token" not in response.json()  # 다시 로그인한다 (A30)

    again = await client.post(f"{API}/email-code", json={"email": EMAIL})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_already_registered"


async def test_signup_cohorts_lists_only_open_cohorts(client: AsyncClient) -> None:
    open_cohort = await create_cohort()
    ended = await create_cohort()
    await CohortModel.filter(id=ended.id).update(status=CohortStatus.ENDED)

    response = await client.get(f"{API}/cohorts")

    assert response.status_code == 200
    ids = [item["cohort_id"] for item in response.json()]
    assert str(open_cohort.id) in ids
    assert str(ended.id) not in ids


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"email": "kim@naver.com"}, 422, "email_domain_not_allowed"),
        ({"email": "not-an-email"}, 422, "invalid_email"),
    ],
)
async def test_email_code_validation(
    client: AsyncClient,
    senders: tuple[InMemoryMailSender, InMemorySmsSender],
    body: dict[str, str],
    status: int,
    code: str,
) -> None:
    response = await client.post(f"{API}/email-code", json=body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_resend_too_soon_returns_429_with_retry_after(
    client: AsyncClient, senders: tuple[InMemoryMailSender, InMemorySmsSender]
) -> None:
    assert (await client.post(f"{API}/email-code", json={"email": EMAIL})).status_code == 204
    response = await client.post(f"{API}/email-code", json={"email": EMAIL})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "resend_too_soon"
    assert 1 <= int(response.headers["retry-after"]) <= 60


async def test_forwarded_for_is_ignored_without_trusted_proxy(
    client: AsyncClient, settings: Settings, senders: tuple[InMemoryMailSender, InMemorySmsSender]
) -> None:
    """신뢰 프록시가 없으면 X-Forwarded-For를 바꿔도 같은 IP로 센다(IP당 20회)."""
    assert settings.trusted_proxies == []
    for n in range(20):
        sent = await client.post(
            f"{API}/email-code",
            json={"email": f"user{n}@gmail.com"},
            headers={"X-Forwarded-For": f"9.9.9.{n}"},
        )
        assert sent.status_code == 204
    blocked = await client.post(
        f"{API}/email-code",
        json={"email": "user99@gmail.com"},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


async def test_duplicate_phone_and_missing_phone_step(
    client: AsyncClient, senders: tuple[InMemoryMailSender, InMemorySmsSender]
) -> None:
    await create_user(email="other@gmail.com", phone_number="01012345678")
    mail, _ = senders
    await client.post(f"{API}/email-code", json={"email": EMAIL})
    token = (
        await client.post(
            f"{API}/email-code/verify", json={"email": EMAIL, "code": _code(mail.sent[-1].text)}
        )
    ).json()["signup_token"]

    duplicate = await client.post(
        f"{API}/phone-code", json={"signup_token": token, "phone_number": "01012345678"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "phone_already_registered"

    no_phone = await client.post(
        API,
        json={
            "signup_token": token,
            "name": "멘토",
            "password": "abcd123!",
            "signup_type": "MENTOR",
        },
    )
    assert no_phone.json()["error"]["code"] == "phone_verification_required"


async def test_invalid_code_format_is_422(client: AsyncClient) -> None:
    response = await client.post(f"{API}/email-code/verify", json={"email": EMAIL, "code": "12ab"})
    assert response.status_code == 422

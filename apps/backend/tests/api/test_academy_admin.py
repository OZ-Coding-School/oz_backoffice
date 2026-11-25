"""학사 마스터 관리 API (실제 DB)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

API = "/api/v1/admin"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _post(
    client: AsyncClient, path: str, body: dict[str, object], h: dict[str, str]
) -> dict[str, Any]:
    response = await client.post(f"{API}{path}", json=body, headers=h)
    assert response.status_code == 201, response.text
    body_json: dict[str, Any] = response.json()
    return body_json


async def test_hierarchy_crud(client: AsyncClient, admin: dict[str, str]) -> None:
    hrd = await _post(
        client,
        "/hrd-bootcamps",
        {"name": "백엔드 KDT", "hrd_net_id": "AIG1", "train_type": "KDT"},
        admin,
    )
    assert (hrd["weekend_se"], hrd["day_night_se"]) == ("WEEKDAY", "DAY")
    hrd_cohort = await _post(
        client,
        f"/hrd-bootcamps/{hrd['id']}/cohorts",
        {"cohort_number": 1, "train_start_date": "2026-11-01"},
        admin,
    )
    bootcamp = await _post(
        client,
        "/bootcamps",
        {"hrd_net_bootcamp_id": hrd["id"], "name": "백엔드", "code": "ah"},
        admin,
    )
    assert bootcamp["code"] == "AH"
    assert (bootcamp["hrd_net_id"], bootcamp["hrd_bootcamp_name"]) == ("AIG1", "백엔드 KDT")  # A97
    cohort = await _post(
        client,
        f"/bootcamps/{bootcamp['id']}/cohorts",
        {
            "hrd_net_cohort_id": hrd_cohort["id"],
            "cohort_number": 3,
            "start_date": "2026-11-01",
            "end_date": "2027-04-30",
        },
        admin,
    )
    assert cohort["status"] == "PLANNED"
    assert (cohort["hrd_net_id"], cohort["hrd_cohort_number"]) == ("AIG1", 1)  # A97

    patched = await client.patch(
        f"{API}/cohorts/{cohort['id']}",
        json={"status": "ONGOING", "discord_guild_id": "1234"},
        headers=admin,
    )
    assert (patched.json()["status"], patched.json()["discord_guild_id"]) == ("ONGOING", "1234")
    cleared = await client.patch(
        f"{API}/hrd-bootcamps/{hrd['id']}", json={"hrd_net_id": None}, headers=admin
    )
    assert cleared.json()["hrd_net_id"] is None
    listed = await client.get(f"{API}/bootcamps/{bootcamp['id']}/cohorts", headers=admin)
    assert [(c["id"], c["hrd_net_id"]) for c in listed.json()] == [(cohort["id"], None)]

    in_use = await client.delete(f"{API}/bootcamps/{bootcamp['id']}", headers=admin)
    assert (in_use.status_code, in_use.json()["error"]["code"]) == (409, "in_use")
    inactive = await client.patch(
        f"{API}/bootcamps/{bootcamp['id']}", json={"is_active": False}, headers=admin
    )
    assert inactive.json()["is_active"] is False
    assert (await client.get(f"{API}/bootcamps", headers=admin)).json() == []
    assert (
        len(
            (
                await client.get(
                    f"{API}/bootcamps", params={"include_inactive": True}, headers=admin
                )
            ).json()
        )
        == 1
    )


async def test_cohort_validation(client: AsyncClient, admin: dict[str, str]) -> None:
    hrd = await _post(client, "/hrd-bootcamps", {"name": "HRD A"}, admin)
    other = await _post(client, "/hrd-bootcamps", {"name": "HRD B"}, admin)
    hrd_cohort = await _post(
        client, f"/hrd-bootcamps/{hrd['id']}/cohorts", {"cohort_number": 1}, admin
    )
    other_cohort = await _post(
        client, f"/hrd-bootcamps/{other['id']}/cohorts", {"cohort_number": 1}, admin
    )
    bootcamp = await _post(
        client,
        "/bootcamps",
        {"hrd_net_bootcamp_id": hrd["id"], "name": "백엔드", "code": "AH"},
        admin,
    )
    url = f"{API}/bootcamps/{bootcamp['id']}/cohorts"
    base = {
        "hrd_net_cohort_id": hrd_cohort["id"],
        "cohort_number": 1,
        "start_date": "2026-11-01",
        "end_date": "2027-04-30",
    }
    await _post(client, f"/bootcamps/{bootcamp['id']}/cohorts", base, admin)

    cases = [
        (base, 409, "cohort_number_taken"),
        ({**base, "cohort_number": 2, "start_date": "2027-05-01"}, 422, "invalid_cohort"),
        (
            {**base, "cohort_number": 2, "hrd_net_cohort_id": str(new_id())},
            404,
            "hrd_cohort_not_found",
        ),
    ]
    for body, status, code in cases:
        response = await client.post(url, json=body, headers=admin)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), body
    # 다른 HRD 과정의 회차에도 연결할 수 있다 (D6)
    crossed = await client.post(
        url,
        json={**base, "cohort_number": 3, "hrd_net_cohort_id": other_cohort["id"]},
        headers=admin,
    )
    assert crossed.status_code == 201
    invalid_guild = await client.post(
        url, json={**base, "cohort_number": 5, "discord_guild_id": "abc"}, headers=admin
    )
    assert invalid_guild.status_code == 422
    assert (
        await client.post(f"{API}/bootcamps/{new_id()}/cohorts", json=base, headers=admin)
    ).status_code == 404


async def test_requires_org_manage(client: AsyncClient, settings: Settings) -> None:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    assert (
        await client.get(f"{API}/hrd-bootcamps", headers=bearer(settings, user))
    ).status_code == 403
    assert (await client.get(f"{API}/bootcamps")).status_code == 401

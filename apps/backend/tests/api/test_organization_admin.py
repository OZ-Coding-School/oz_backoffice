"""조직 마스터 관리 API (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.organization import create_employee

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_department_crud(client: AsyncClient, admin: dict[str, str]) -> None:
    url = "/api/v1/admin/departments"
    root = (
        await client.post(url, json={"name": "교육본부", "description": "교육"}, headers=admin)
    ).json()
    team = await client.post(
        url, json={"name": "1팀", "description": "운영", "parent_id": root["id"]}, headers=admin
    )
    assert team.status_code == 201
    team_id = team.json()["id"]

    renamed = await client.patch(f"{url}/{team_id}", json={"name": "운영 1팀"}, headers=admin)
    assert (renamed.json()["name"], renamed.json()["parent_id"]) == ("운영 1팀", root["id"])
    # parent_id를 null로 보내면 최상위로 옮긴다 (보내지 않으면 그대로)
    top = await client.patch(f"{url}/{team_id}", json={"parent_id": None}, headers=admin)
    assert top.json()["parent_id"] is None
    cycle = await client.patch(f"{url}/{root['id']}", json={"parent_id": root["id"]}, headers=admin)
    assert cycle.status_code == 422

    listed = (await client.get(url, headers=admin)).json()
    assert {d["name"] for d in listed} == {"교육본부", "운영 1팀"}
    duplicate = await client.post(url, json={"name": "교육본부", "description": "x"}, headers=admin)
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (
        409,
        "department_name_taken",
    )
    assert (await client.delete(f"{url}/{team_id}", headers=admin)).status_code == 204
    assert (await client.delete(f"{url}/{new_id()}", headers=admin)).status_code == 404


async def test_positions_and_in_use(client: AsyncClient, admin: dict[str, str]) -> None:
    url = "/api/v1/admin/positions"
    created = await client.post(url, json={"name": "매니저", "priority": 3}, headers=admin)
    assert created.status_code == 201
    updated = await client.patch(
        f"{url}/{created.json()['id']}", json={"priority": 1}, headers=admin
    )
    assert updated.json() == {**created.json(), "priority": 1}
    assert (
        await client.post(url, json={"name": "x", "priority": -1}, headers=admin)
    ).status_code == 422

    employee = await create_employee()
    in_use = await client.delete(f"{url}/{employee.position_id}", headers=admin)
    assert (in_use.status_code, in_use.json()["error"]["code"]) == (409, "in_use")


async def test_employees_list_and_transfer(client: AsyncClient, admin: dict[str, str]) -> None:
    employee = await create_employee()
    department = (
        await client.post(
            "/api/v1/admin/departments", json={"name": "2팀", "description": "운영"}, headers=admin
        )
    ).json()

    page = (await client.get("/api/v1/admin/employees", headers=admin)).json()
    assert page["total"] == 1
    assert page["items"][0]["user"]["id"] == str(employee.user_id)

    moved = await client.patch(
        f"/api/v1/admin/employees/{employee.id}",
        json={"department_id": department["id"], "employment_type": "CONTRACT"},
        headers=admin,
    )
    assert moved.status_code == 200
    assert (moved.json()["department_id"], moved.json()["employment_type"]) == (
        department["id"],
        "CONTRACT",
    )
    filtered = await client.get(
        "/api/v1/admin/employees", params={"department_id": department["id"]}, headers=admin
    )
    assert filtered.json()["total"] == 1
    assert (
        await client.get(f"/api/v1/admin/employees/{new_id()}", headers=admin)
    ).status_code == 404


async def test_requires_org_manage(client: AsyncClient, settings: Settings) -> None:
    employee = await create_employee()
    users = TortoiseUserRepository()
    user = await users.get(employee.user_id)
    assert user is not None
    user.approve(now=datetime.now(UTC))
    await users.save(user)
    assert (
        await client.get("/api/v1/admin/departments", headers=bearer(settings, user))
    ).status_code == 403
    assert (await client.get("/api/v1/admin/departments")).status_code == 401

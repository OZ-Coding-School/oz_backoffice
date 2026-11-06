"""과정·기수 담당자 관리 API (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.organization import create_employee

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _approved_bearer(settings: Settings, user_id: object) -> dict[str, str]:
    users = TortoiseUserRepository()
    user = await users.get(user_id)  # type: ignore[arg-type]
    assert user is not None
    user.approve(now=datetime.now(UTC))
    await users.save(user)
    return bearer(settings, user)


async def test_cohort_staff_lifecycle_controls_permissions(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    url = f"/api/v1/admin/cohorts/{cohort.id}/staffs"

    created = await client.post(
        url, json={"employee_id": str(employee.id), "role": "MANAGER"}, headers=admin
    )
    assert created.status_code == 201
    staff = created.json()
    assert staff["role"] == "MANAGER"
    assert staff["user"]["id"] == str(employee.user_id)

    listed = await client.get(url, headers=admin)
    assert [s["id"] for s in listed.json()] == [staff["id"]]

    manager = await _approved_bearer(settings, employee.user_id)
    me = (await client.get("/api/v1/me", headers=manager)).json()
    assert me["roles"][0]["role"] == "COHORT_MANAGER"
    # 담당자 관리는 SUPER_ADMIN만 (매니저는 403)
    assert (await client.get(url, headers=manager)).status_code == 403

    deleted = await client.delete(f"{url}/{staff['id']}", headers=admin)
    assert deleted.status_code == 204
    assert (await client.get(url, headers=admin)).json() == []
    assert (await client.get("/api/v1/me", headers=manager)).json()["roles"] == []


async def test_bootcamp_staff_and_errors(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    url = f"/api/v1/admin/bootcamps/{cohort.bootcamp_id}/staffs"
    body = {"employee_id": str(employee.id), "role": "ASSISTANT"}

    assert (await client.post(url, json=body, headers=admin)).status_code == 201
    duplicate = await client.post(url, json=body, headers=admin)
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (
        409,
        "staff_already_assigned",
    )
    unknown_employee = await client.post(
        url, json={"employee_id": str(new_id()), "role": "MANAGER"}, headers=admin
    )
    assert unknown_employee.status_code == 404
    unknown_target = await client.post(
        f"/api/v1/admin/bootcamps/{new_id()}/staffs", json=body, headers=admin
    )
    assert unknown_target.json()["error"]["code"] == "invalid_staff_target"
    assert (await client.delete(f"{url}/{new_id()}", headers=admin)).status_code == 404
    assert (
        await client.post(url, json={**body, "role": "OWNER"}, headers=admin)
    ).status_code == 422
    assert (await client.get(url)).status_code == 401

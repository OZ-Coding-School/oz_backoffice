"""직위 = 역할 (decisions A87): 직위 권한·데이터 범위 API와 그 효과 (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import assign, give_permissions
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def staff() -> User:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_position_permissions_and_data_scope_drive_access(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    created = await client.post(
        "/api/v1/admin/positions",
        json={"name": "감사 담당", "priority": 7, "data_scope": "ASSIGNED"},
        headers=admin,
    )
    assert created.status_code == 201
    position = created.json()
    assert (position["permissions"], position["employee_count"]) == ([], 0)

    cohort, other = await create_cohort(), await create_cohort()
    user = await staff()
    employee = await give_permissions(user.id, set())
    await client.patch(
        f"/api/v1/admin/employees/{employee.id}",
        json={"position_id": position["id"]},
        headers=admin,
    )
    await assign(employee, cohort_ids=(cohort.id,))
    headers = bearer(settings, user)
    requests = "/api/v1/admin/cohorts/{}/mentoring/requests"
    assert (await client.get(requests.format(cohort.id), headers=headers)).status_code == 403

    updated = await client.put(
        f"/api/v1/admin/positions/{position['id']}/permissions",
        json={"permissions": ["mentoring.request.read", "org.department.read"]},
        headers=admin,
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == ["org.department.read", "mentoring.request.read"]
    assert updated.json()["employee_count"] == 1
    # 기수 엔터티는 담당 기수만, 기수와 무관한 엔터티는 전체 (A87)
    assert (await client.get(requests.format(cohort.id), headers=headers)).status_code == 200
    assert (await client.get(requests.format(other.id), headers=headers)).status_code == 403
    assert (await client.get("/api/v1/admin/departments", headers=headers)).status_code == 200

    await client.patch(
        f"/api/v1/admin/positions/{position['id']}", json={"data_scope": "ALL"}, headers=admin
    )
    assert (await client.get(requests.format(other.id), headers=headers)).status_code == 200
    # 직원 응답에도 직위의 데이터 범위가 보인다 (A91)
    row = (await client.get(f"/api/v1/admin/employees/{employee.id}", headers=admin)).json()
    assert row["data_scope"] == "ALL"


async def test_permission_rules_and_catalog(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    position = (
        await client.post(
            "/api/v1/admin/positions", json={"name": "보조", "priority": 8}, headers=admin
        )
    ).json()
    url = f"/api/v1/admin/positions/{position['id']}/permissions"

    async def code(permissions: list[str]) -> tuple[int, str]:
        res = await client.put(url, json={"permissions": permissions}, headers=admin)
        return res.status_code, res.json()["error"]["code"]

    assert await code(["mentoring.team.manage"]) == (422, "permission_requires_read")
    assert await code(["nope"]) == (422, "permission_not_found")

    catalog = (await client.get("/api/v1/admin/permissions", headers=admin)).json()
    assert len(catalog) == 40
    manage = next(p for p in catalog if p["code"] == "mentoring.team.manage")
    assert (manage["entity"], manage["cohort_bound"], manage["requires"]) == (
        "멘토링 팀",
        True,
        "mentoring.team.read",
    )

    viewer = await staff()
    await give_permissions(viewer.id, {"org.position.read", "access.role.read"})
    headers = bearer(settings, viewer)
    assert (await client.get("/api/v1/admin/permissions", headers=headers)).status_code == 200
    denied = await client.put(url, json={"permissions": []}, headers=headers)
    assert denied.status_code == 403
    assert (await client.get("/api/v1/admin/permissions")).status_code == 401

"""조직 마스터 관리 API (실제 DB)."""

import uuid
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
from tests.factories.organization import create_employee, create_team

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
    created = await client.post(
        url, json={"name": "교육본부", "description": "교육"}, headers=admin
    )
    assert created.status_code == 201
    assert "parent_id" not in created.json()
    department_id = created.json()["id"]

    renamed = await client.patch(
        f"{url}/{department_id}", json={"name": "운영본부", "rules": "규칙"}, headers=admin
    )
    assert (renamed.json()["name"], renamed.json()["rules"]) == ("운영본부", "규칙")
    cleared = await client.patch(f"{url}/{department_id}", json={"rules": None}, headers=admin)
    assert (cleared.json()["name"], cleared.json()["rules"]) == ("운영본부", None)

    listed = (await client.get(url, headers=admin)).json()
    assert [d["name"] for d in listed] == ["운영본부"]
    duplicate = await client.post(url, json={"name": "운영본부", "description": "x"}, headers=admin)
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (
        409,
        "department_name_taken",
    )
    assert (await client.delete(f"{url}/{department_id}", headers=admin)).status_code == 204
    assert (await client.delete(f"{url}/{new_id()}", headers=admin)).status_code == 404


async def test_team_crud_and_bootcamp_team(client: AsyncClient, admin: dict[str, str]) -> None:
    department = (
        await client.post(
            "/api/v1/admin/departments",
            json={"name": "교육본부", "description": "교육"},
            headers=admin,
        )
    ).json()
    url = "/api/v1/admin/teams"
    created = await client.post(
        url, json={"department_id": department["id"], "name": "교육 1팀"}, headers=admin
    )
    assert created.status_code == 201
    team = created.json()
    assert team == {
        "id": team["id"],
        "department_id": department["id"],
        "name": "교육 1팀",
        "description": None,
        "bootcamp_ids": [],
    }
    duplicate = await client.post(
        url, json={"department_id": department["id"], "name": "교육 1팀"}, headers=admin
    )
    assert (duplicate.status_code, duplicate.json()["error"]["code"]) == (409, "team_name_taken")

    cohort = await create_cohort()
    assigned = await client.put(
        f"/api/v1/admin/bootcamps/{cohort.bootcamp_id}/team",
        json={"team_id": team["id"]},
        headers=admin,
    )
    assert assigned.json() == {"bootcamp_id": str(cohort.bootcamp_id), "team_id": team["id"]}
    described = await client.patch(
        f"{url}/{team['id']}", json={"description": "운영"}, headers=admin
    )
    assert (described.json()["description"], described.json()["bootcamp_ids"]) == (
        "운영",
        [str(cohort.bootcamp_id)],
    )
    in_use = await client.delete(f"{url}/{team['id']}", headers=admin)
    assert (in_use.status_code, in_use.json()["error"]["code"]) == (409, "team_in_use")
    target = (
        await client.post(
            url, json={"department_id": department["id"], "name": "교육 2팀"}, headers=admin
        )
    ).json()
    moved = await client.delete(
        f"{url}/{team['id']}", params={"move_to_team_id": target["id"]}, headers=admin
    )
    assert moved.status_code == 204
    teams = (await client.get(url, headers=admin)).json()
    assert [(t["name"], t["bootcamp_ids"]) for t in teams] == [
        ("교육 2팀", [str(cohort.bootcamp_id)])
    ]
    team = target

    unassigned = await client.put(
        f"/api/v1/admin/bootcamps/{cohort.bootcamp_id}/team", json={"team_id": None}, headers=admin
    )
    assert unassigned.json()["team_id"] is None
    assert (await client.get(url, headers=admin)).json()[0]["bootcamp_ids"] == []
    missing = await client.put(
        f"/api/v1/admin/bootcamps/{new_id()}/team", json={"team_id": team["id"]}, headers=admin
    )
    assert missing.status_code == 404
    assert (await client.delete(f"{url}/{team['id']}", headers=admin)).status_code == 204


async def test_positions_and_in_use(client: AsyncClient, admin: dict[str, str]) -> None:
    url = "/api/v1/admin/positions"
    created = await client.post(
        url, json={"name": "매니저", "priority": 3, "assignment_scope": "COURSE"}, headers=admin
    )
    assert created.status_code == 201
    assert created.json()["assignment_scope"] == "COURSE"
    updated = await client.patch(
        f"{url}/{created.json()['id']}", json={"priority": 1}, headers=admin
    )
    assert updated.json() == {**created.json(), "priority": 1}
    cleared = await client.patch(
        f"{url}/{created.json()['id']}", json={"assignment_scope": None}, headers=admin
    )
    assert cleared.json()["assignment_scope"] is None
    invalid = await client.patch(
        f"{url}/{created.json()['id']}", json={"assignment_scope": "TEAM"}, headers=admin
    )
    assert invalid.status_code == 422
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

    team = await create_team(uuid.UUID(department["id"]))
    moved = await client.patch(
        f"/api/v1/admin/employees/{employee.id}",
        json={
            "department_id": department["id"],
            "team_id": str(team.id),
            "employment_type": "CONTRACT",
        },
        headers=admin,
    )
    assert moved.status_code == 200
    assert (
        moved.json()["department_id"],
        moved.json()["team_id"],
        moved.json()["employment_type"],
    ) == (department["id"], str(team.id), "CONTRACT")
    direct = await client.patch(
        f"/api/v1/admin/employees/{employee.id}", json={"team_id": None}, headers=admin
    )
    assert (direct.json()["department_id"], direct.json()["team_id"]) == (department["id"], None)
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


async def test_employees_search_team_and_assignments(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    """직원 목록: 이름·이메일 검색, 팀 필터, 담당 (A83). 팀리드는 조회만."""
    from tests.factories.access import TEAM_LEAD, give_role
    from tests.factories.identity import make_user

    users = TortoiseUserRepository()
    kim = make_user(name="김운영", email="kim.manager@nextrunners.co.kr")
    lee = make_user(name="이조교", email="lee@nextrunners.co.kr")
    for u in (kim, lee):
        await users.add(u)
    manager, assistant = await create_employee(kim), await create_employee(lee)
    cohort = await create_cohort(cohort_number=12)
    staffs = "/api/v1/admin"
    assert (
        await client.post(
            f"{staffs}/bootcamps/{cohort.bootcamp_id}/staffs",
            json={"employee_id": str(manager.id), "role": "MANAGER"},
            headers=admin,
        )
    ).status_code in (200, 201)
    assert (
        await client.post(
            f"{staffs}/cohorts/{cohort.id}/staffs",
            json={"employee_id": str(assistant.id), "role": "ASSISTANT"},
            headers=admin,
        )
    ).status_code in (200, 201)

    url = "/api/v1/admin/employees"
    by_name = (await client.get(url, params={"q": "김운"}, headers=admin)).json()
    assert [e["id"] for e in by_name["items"]] == [str(manager.id)]
    (assignment,) = by_name["items"][0]["assignments"]
    assert (assignment["role"], assignment["bootcamp_id"], assignment["cohort_id"]) == (
        "MANAGER",
        str(cohort.bootcamp_id),
        None,
    )
    assert assignment["bootcamp_name"]
    by_email = (await client.get(url, params={"q": "lee@"}, headers=admin)).json()
    (row,) = by_email["items"]
    assert (row["assignments"][0]["cohort_id"], row["assignments"][0]["cohort_number"]) == (
        str(cohort.id),
        12,
    )

    team = await create_team(manager.department_id)
    await client.patch(f"{url}/{manager.id}", json={"team_id": str(team.id)}, headers=admin)
    in_team = (await client.get(url, params={"team_id": str(team.id)}, headers=admin)).json()
    assert [e["id"] for e in in_team["items"]] == [str(manager.id)]
    lead = make_user(email="lead@nextrunners.co.kr")
    lead.approve(now=datetime.now(UTC))
    await users.add(lead)
    await give_role(lead.id, TEAM_LEAD)
    viewer = bearer(settings, lead)
    assert (await client.get(url, headers=viewer)).status_code == 200
    assert (await client.get(f"{url}/{manager.id}", headers=viewer)).status_code == 200
    assert (
        await client.patch(f"{url}/{manager.id}", json={"team_id": None}, headers=viewer)
    ).status_code == 403

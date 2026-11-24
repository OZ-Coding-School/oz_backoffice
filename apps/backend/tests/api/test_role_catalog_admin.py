"""역할·권한 관리 API (실제 DB, decisions A84)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import TEAM_LEAD
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

URL = "/api/v1/admin/roles"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def staff_with(role: str, scope: RoleScopeType, scope_id: object = None) -> User:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        user.id,
        role,
        scope,
        scope_id,  # type: ignore[arg-type]
    )
    return user


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_catalog_lists_staff_roles_and_permissions(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    body = (await client.get(URL, headers=admin)).json()

    codes = [r["code"] for r in body["roles"]]
    assert codes == ["SUPER_ADMIN", "TEAM_LEAD", "COHORT_MANAGER", "COHORT_ASSISTANT"]
    super_admin = body["roles"][0]
    assert (super_admin["permissions_editable"], super_admin["builtin"]) == (False, True)
    assert super_admin["holder_count"] == 1
    assert len(super_admin["permissions"]) == len(body["permissions"])
    manager = body["roles"][2]
    assert manager["scope_kind"] == "SCOPED"
    assert manager["permissions_editable"]
    global_only = {p["code"] for p in body["permissions"] if p["global_only"]}
    assert global_only == {"org.manage", "role.assign", "staff.assign"}


async def test_custom_role_lifecycle_controls_access(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    created = await client.post(
        URL,
        json={"code": "ORG_EDITOR", "name": "조직 편집", "scope_kind": "GLOBAL"},
        headers=admin,
    )
    assert created.status_code == 201
    assert (created.json()["permissions"], created.json()["builtin"]) == ([], False)

    holder = await staff_with("ORG_EDITOR", RoleScopeType.GLOBAL)
    headers = bearer(settings, holder)
    assert (await client.get("/api/v1/admin/departments", headers=headers)).status_code == 403

    granted = await client.put(
        f"{URL}/ORG_EDITOR/permissions", json={"permissions": ["org.manage"]}, headers=admin
    )
    assert granted.json()["permissions"] == ["org.manage"]
    assert (await client.get("/api/v1/admin/departments", headers=headers)).status_code == 200

    in_use = await client.delete(f"{URL}/ORG_EDITOR", headers=admin)
    assert (in_use.status_code, in_use.json()["error"]["code"]) == (409, "role_in_use")

    renamed = await client.patch(
        f"{URL}/ORG_EDITOR", json={"name": "조직 관리", "description": "부서·팀"}, headers=admin
    )
    assert (renamed.json()["name"], renamed.json()["description"]) == ("조직 관리", "부서·팀")
    assert await AuditLogModel.filter(action__startswith="access.role_definition.").count() == 3


async def test_editing_builtin_role_changes_its_holders(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    lead = bearer(settings, await staff_with(TEAM_LEAD, RoleScopeType.GLOBAL))
    staff_url = f"/api/v1/admin/cohorts/{new_id()}/staffs"
    assert (await client.get(staff_url, headers=lead)).status_code != 403

    current = next(
        r for r in (await client.get(URL, headers=admin)).json()["roles"] if r["code"] == TEAM_LEAD
    )
    narrowed = [p for p in current["permissions"] if p != "staff.assign"]
    await client.put(f"{URL}/TEAM_LEAD/permissions", json={"permissions": narrowed}, headers=admin)
    assert (await client.get(staff_url, headers=lead)).status_code == 403


async def test_rule_violations(client: AsyncClient, admin: dict[str, str]) -> None:
    async def error(method: str, url: str, json: object = None) -> tuple[int, str]:
        response = await client.request(method, url, json=json, headers=admin)
        return response.status_code, response.json()["error"]["code"]

    new = {"code": "HELPER", "name": "도우미", "scope_kind": "SCOPED"}
    assert (await client.post(URL, json=new, headers=admin)).status_code == 201
    assert await error("POST", URL, new) == (409, "role_code_taken")
    assert await error("POST", URL, {**new, "code": "HELPER_2"}) == (409, "role_name_taken")
    assert await error("POST", URL, {**new, "code": "helper"}) == (422, "invalid_role_code")
    assert await error("PATCH", f"{URL}/HELPER", {"name": "운영 매니저"}) == (
        409,
        "role_name_taken",
    )
    assert await error("PUT", f"{URL}/HELPER/permissions", {"permissions": ["org.manage"]}) == (
        422,
        "global_only_permission",
    )
    assert await error("PUT", f"{URL}/SUPER_ADMIN/permissions", {"permissions": []}) == (
        422,
        "role_permissions_locked",
    )
    assert await error("DELETE", f"{URL}/COHORT_MANAGER") == (422, "builtin_role")
    assert await error("PUT", f"{URL}/MENTOR/permissions", {"permissions": []}) == (
        404,
        "role_not_found",
    )
    assert await error("DELETE", f"{URL}/NOPE") == (404, "role_not_found")
    assert (await client.delete(f"{URL}/HELPER", headers=admin)).status_code == 204
    assert [r["code"] for r in (await client.get(URL, headers=admin)).json()["roles"]][-1] == (
        "COHORT_ASSISTANT"
    )


async def test_only_role_assign_can_use(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    lead = bearer(settings, await staff_with(TEAM_LEAD, RoleScopeType.GLOBAL))
    assert (await client.get(URL, headers=lead)).status_code == 403
    assert (await client.get(URL)).status_code == 401

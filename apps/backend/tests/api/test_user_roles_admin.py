"""회원 역할 관리 API (실제 DB)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def approved_user() -> User:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


@pytest.fixture
async def boss(settings: Settings) -> tuple[User, dict[str, str]]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return result.user, bearer(settings, result.user)


async def test_grant_and_revoke_super_admin(
    client: AsyncClient, boss: tuple[User, dict[str, str]], settings: Settings
) -> None:
    _, admin = boss
    target = await approved_user()
    url = f"/api/v1/admin/users/{target.id}/roles"
    expires = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    granted = await client.post(
        url, json={"role": "SUPER_ADMIN", "expires_at": expires}, headers=admin
    )
    assert granted.status_code == 201
    assert (granted.json()["managed_by"], granted.json()["is_effective"]) == ("direct", True)
    # 부여받은 회원은 바로 관리 API를 쓸 수 있다
    assert (await client.get(url, headers=bearer(settings, target))).status_code == 200

    revoked = await client.delete(f"{url}/{granted.json()['id']}", headers=admin)
    assert revoked.status_code == 204
    assert (await client.get(url, headers=admin)).json() == []
    assert (await client.get(url, headers=bearer(settings, target))).status_code == 403


async def test_staff_roles_are_listed_but_not_editable(
    client: AsyncClient, boss: tuple[User, dict[str, str]]
) -> None:
    _, admin = boss
    target = await approved_user()
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        target.id, COHORT_ASSISTANT, RoleScopeType.COHORT, new_id()
    )
    url = f"/api/v1/admin/users/{target.id}/roles"

    (staff_role,) = (await client.get(url, headers=admin)).json()
    assert (staff_role["role"], staff_role["managed_by"]) == ("COHORT_ASSISTANT", "assignment")
    grant = await client.post(url, json={"role": "COHORT_ASSISTANT"}, headers=admin)
    assert grant.json()["error"]["code"] == "role_managed_by_assignment"
    revoke = await client.delete(f"{url}/{staff_role['id']}", headers=admin)
    assert revoke.json()["error"]["code"] == "role_managed_by_assignment"


async def test_last_super_admin_and_errors(
    client: AsyncClient, boss: tuple[User, dict[str, str]]
) -> None:
    me, admin = boss
    url = f"/api/v1/admin/users/{me.id}/roles"
    (own,) = (await client.get(url, headers=admin)).json()

    last = await client.delete(f"{url}/{own['id']}", headers=admin)
    assert (last.status_code, last.json()["error"]["code"]) == (409, "last_super_admin")
    assert (
        await client.get(f"/api/v1/admin/users/{new_id()}/roles", headers=admin)
    ).status_code == 404
    pending = await create_applicant()
    not_approved = await client.post(
        f"/api/v1/admin/users/{pending.id}/roles", json={"role": "SUPER_ADMIN"}, headers=admin
    )
    assert not_approved.json()["error"]["code"] == "user_not_approved"
    assert (await client.get(url)).status_code == 401

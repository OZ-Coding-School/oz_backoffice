"""최고 관리자 켜기·끄기 (decisions A87): 최고 관리자만, 운영진만, 마지막 1명 보호."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.access import TEAM_LEAD, give_role
from tests.factories.identity import make_user
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def approved(user: User) -> User:
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().add(user)
    return user


async def test_toggle_super_admin(client: AsyncClient, settings: Settings) -> None:
    boss = (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    admin = bearer(settings, boss)
    staff = await create_applicant()
    staff.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(staff)
    url = f"/api/v1/admin/users/{staff.id}/super-admin"

    on = await client.put(url, json={"enabled": True}, headers=admin)
    assert on.json() == {"user_id": str(staff.id), "is_super_admin": True}
    me = (await client.get("/api/v1/me", headers=bearer(settings, staff))).json()
    assert me["is_super_admin"] is True
    # 새 최고 관리자는 모든 권한
    assert (
        await client.get("/api/v1/admin/departments", headers=bearer(settings, staff))
    ).status_code == 200

    # 이제 둘이므로 처음 관리자를 끌 수 있고, 남은 한 명은 끌 수 없다
    off = await client.put(
        f"/api/v1/admin/users/{boss.id}/super-admin",
        json={"enabled": False},
        headers=bearer(settings, staff),
    )
    assert off.json()["is_super_admin"] is False
    last = await client.put(url, json={"enabled": False}, headers=bearer(settings, staff))
    assert (last.status_code, last.json()["error"]["code"]) == (409, "last_super_admin")
    actions = await AuditLogModel.filter(action__startswith="access.super_admin.").count()
    assert actions == 3  # CLI + 켜기 + 끄기


async def test_only_super_admin_and_only_staff(client: AsyncClient, settings: Settings) -> None:
    boss = (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    lead = await create_applicant()
    lead.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(lead)
    await give_role(lead.id, TEAM_LEAD)  # 모든 데이터 직위여도 최고 관리자는 아니다
    student = await approved(make_user())
    url = f"/api/v1/admin/users/{student.id}/super-admin"

    denied = await client.put(url, json={"enabled": True}, headers=bearer(settings, lead))
    assert (denied.status_code, denied.json()["error"]["code"]) == (403, "super_admin_only")
    not_staff = await client.put(url, json={"enabled": True}, headers=bearer(settings, boss))
    assert (not_staff.status_code, not_staff.json()["error"]["code"]) == (422, "staff_only")
    assert (await client.put(url, json={"enabled": True})).status_code == 401

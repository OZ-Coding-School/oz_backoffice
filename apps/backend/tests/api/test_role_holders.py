"""역할 보유자 목록·새 역할 직접 부여 API (실제 DB, decisions A85)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT, STUDENT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.organization import create_employee
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

URL = "/api/v1/admin/role-holders"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def staff(name: str) -> User:
    user = await create_applicant(name=name)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings, name="가관리")
    return bearer(settings, result.user)


async def test_holders_are_listed_per_person(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    created = await client.post(
        "/api/v1/admin/roles",
        json={"code": "AUDITOR", "name": "감사", "scope_kind": "SCOPED"},
        headers=admin,
    )
    assert created.status_code == 201

    bora = await staff("나보라")
    await create_employee(bora)
    roles = RoleAssignmentService(TortoiseUserRoleRepository())
    await roles.grant(bora.id, COHORT_ASSISTANT, RoleScopeType.COHORT, cohort.id)
    await roles.grant(bora.id, STUDENT, RoleScopeType.COHORT, cohort.id)  # 목록에서 빠짐
    granted = await client.post(
        f"/api/v1/admin/users/{bora.id}/roles",
        json={
            "role": "AUDITOR",
            "scope_type": "BOOTCAMP",
            "scope_id": str(cohort.bootcamp_id),
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        headers=admin,
    )
    assert (granted.status_code, granted.json()["managed_by"]) == (201, "direct")
    await staff("다른사람")  # 역할 없음 → 목록에 없음

    page = (await client.get(URL, headers=admin)).json()
    assert page["total"] == 2
    assert [h["name"] for h in page["items"]] == ["가관리", "나보라"]
    holder = page["items"][1]
    assert holder["department_name"] is not None
    assert holder["position_name"] is not None
    summary = [
        (r["role"], r["role_name"], r["bootcamp_name"], r["cohort_number"], r["managed_by"])
        for r in holder["roles"]
    ]
    bootcamp_name = summary[0][2]
    assert bootcamp_name is not None
    assert bootcamp_name.startswith("운영과정")
    assert summary == [
        ("COHORT_ASSISTANT", "조교", bootcamp_name, 1, "assignment"),
        ("AUDITOR", "감사", bootcamp_name, None, "direct"),
    ]

    filtered = (await client.get(URL, params={"role": "AUDITOR"}, headers=admin)).json()
    assert [h["name"] for h in filtered["items"]] == ["나보라"]
    assert len(filtered["items"][0]["roles"]) == 2  # 그 사람의 다른 역할도 보인다
    searched = (await client.get(URL, params={"q": "보라"}, headers=admin)).json()
    assert searched["total"] == 1
    paged = (await client.get(URL, params={"limit": 1, "offset": 1}, headers=admin)).json()
    assert (paged["total"], [h["name"] for h in paged["items"]]) == (2, ["나보라"])


async def test_expired_grants_are_listed(
    client: AsyncClient, admin: dict[str, str], app: FastAPI
) -> None:
    temp = await staff("임시")
    expires = datetime.now(UTC) + timedelta(hours=1)
    await client.post(
        f"/api/v1/admin/users/{temp.id}/roles",
        json={"role": "TEAM_LEAD", "expires_at": expires.isoformat()},
        headers=admin,
    )
    app.state.clock = FixedClock(expires + timedelta(minutes=1))  # 만료 뒤
    (item,) = (await client.get(URL, params={"role": "TEAM_LEAD"}, headers=admin)).json()["items"]
    assert (item["name"], item["roles"][0]["is_effective"]) == ("임시", False)


async def test_only_role_assign(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    lead = await staff("팀리드")
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        lead.id, "TEAM_LEAD", RoleScopeType.GLOBAL
    )
    assert (await client.get(URL, headers=bearer(settings, lead))).status_code == 403
    assert (await client.get(URL)).status_code == 401

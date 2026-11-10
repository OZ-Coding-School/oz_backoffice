"""기수 멘토링 설정·금지 시간대·추가 휴일 API (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT, COHORT_MANAGER
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.staff_review import create_applicant, seed_roles

pytestmark = pytest.mark.api

API = "/api/v1/admin"
SETTINGS = {
    "allow_team_mentoring": False,
    "allow_1_on_1": True,
    "default_1on1_minutes": 120,
    "default_team_minutes": 0,
    "min_lead_hours": 12,
    "allowed_duration": 60,
    "max_pending_requests": 2,
}


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _staff(settings: Settings, role: str, cohort_id: object) -> dict[str, str]:
    await seed_roles()
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        user.id,
        role,
        RoleScopeType.COHORT,
        cohort_id,  # type: ignore[arg-type]
    )
    return bearer(settings, user)


async def test_settings_require_first_save(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    path = f"{API}/cohorts/{cohort.id}/mentoring-settings"

    missing = await client.get(path, headers=admin)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "mentoring_settings_not_configured"

    saved = await client.put(path, json=SETTINGS, headers=admin)
    assert saved.status_code == 200, saved.text
    assert saved.json()["allowed_duration"] == 60
    updated = await client.put(path, json={**SETTINGS, "max_pending_requests": 3}, headers=admin)
    assert updated.json()["max_pending_requests"] == 3
    assert (await client.get(path, headers=admin)).json()["max_pending_requests"] == 3


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"allow_1_on_1": False}, "mentoring_mode_required"),
        ({"default_1on1_minutes": 90}, "invalid_default_minutes"),
    ],
)
async def test_settings_rules(
    client: AsyncClient, admin: dict[str, str], changes: dict[str, object], code: str
) -> None:
    cohort = await create_cohort()
    response = await client.put(
        f"{API}/cohorts/{cohort.id}/mentoring-settings", json={**SETTINGS, **changes}, headers=admin
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


async def test_settings_reject_unlisted_choices(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    for changes in ({"allowed_duration": 45}, {"min_lead_hours": 48}, {"max_pending_requests": 4}):
        response = await client.put(
            f"{API}/cohorts/{cohort.id}/mentoring-settings",
            json={**SETTINGS, **changes},
            headers=admin,
        )
        assert response.status_code == 422


async def test_block_times_crud_and_overlap(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    path = f"{API}/cohorts/{cohort.id}/mentoring-block-times"
    body = {
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "start_time": "09:00",
        "end_time": "12:00",
        "reason": "오전 수업",
    }
    created = await client.post(path, json=body, headers=admin)
    assert created.status_code == 201, created.text
    assert created.json()["weekdays_only"] is True
    block_id = created.json()["id"]

    afternoon = await client.post(
        path, json={**body, "start_time": "12:00", "end_time": "18:00"}, headers=admin
    )
    assert afternoon.status_code == 201  # 맞닿기만 하면 허용
    overlap = await client.post(
        path, json={**body, "start_time": "11:00", "end_time": "13:00"}, headers=admin
    )
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "block_time_overlap"

    moved = await client.patch(
        f"{path}/{block_id}", json={"start_time": "08:00", "end_time": "11:00"}, headers=admin
    )
    assert moved.json()["start_time"] == "08:00:00"
    clash = await client.patch(f"{path}/{block_id}", json={"end_time": "13:00"}, headers=admin)
    assert clash.status_code == 409

    assert (await client.delete(f"{path}/{block_id}", headers=admin)).status_code == 204
    assert len((await client.get(path, headers=admin)).json()) == 1
    other = await create_cohort()
    wrong_cohort = await client.delete(
        f"{API}/cohorts/{other.id}/mentoring-block-times/{afternoon.json()['id']}", headers=admin
    )
    assert wrong_cohort.status_code == 404


async def test_holidays(client: AsyncClient, admin: dict[str, str]) -> None:
    created = await client.post(
        f"{API}/mentoring-holidays",
        json={"holiday_date": "2026-11-20", "name": "학원 휴무"},
        headers=admin,
    )
    assert created.status_code == 201
    duplicate = await client.post(
        f"{API}/mentoring-holidays",
        json={"holiday_date": "2026-11-20", "name": "중복"},
        headers=admin,
    )
    assert duplicate.json()["error"]["code"] == "holiday_already_exists"

    listed = (
        await client.get(f"{API}/mentoring-holidays", params={"year": 2026}, headers=admin)
    ).json()
    sources = {(h["holiday_date"], h["source"]) for h in listed}
    assert ("2026-11-20", "CUSTOM") in sources
    assert ("2026-09-25", "PUBLIC") in sources  # 추석

    deleted = await client.delete(f"{API}/mentoring-holidays/{created.json()['id']}", headers=admin)
    assert deleted.status_code == 204


async def test_permissions(client: AsyncClient, settings: Settings) -> None:
    mine, other = await create_cohort(), await create_cohort()
    manager = await _staff(settings, COHORT_MANAGER, mine.id)
    assistant = await _staff(settings, COHORT_ASSISTANT, mine.id)

    assert (
        await client.put(
            f"{API}/cohorts/{mine.id}/mentoring-settings", json=SETTINGS, headers=manager
        )
    ).status_code == 200
    assert (
        await client.put(
            f"{API}/cohorts/{other.id}/mentoring-settings", json=SETTINGS, headers=manager
        )
    ).status_code == 403
    assert (
        await client.get(f"{API}/cohorts/{mine.id}/mentoring-settings", headers=assistant)
    ).status_code == 403
    # 추가 휴일은 담당 범위가 있는 매니저도 관리한다 (A34)
    assert (
        await client.post(
            f"{API}/mentoring-holidays",
            json={"holiday_date": "2026-12-24", "name": "휴무"},
            headers=manager,
        )
    ).status_code == 201
    assert (await client.get(f"{API}/mentoring-holidays", params={"year": 2026})).status_code == 401

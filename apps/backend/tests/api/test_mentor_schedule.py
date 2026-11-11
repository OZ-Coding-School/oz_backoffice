"""멘토 불가 시간·신청 받기·기수 운영시간 API (실제 DB, A37)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.time import KST
from tests.factories.academy import create_cohort
from tests.factories.educator import create_mentor, create_user
from tests.factories.staff_review import create_applicant, seed_roles

pytestmark = pytest.mark.api

ME = "/api/v1/me/mentor-schedule"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved(user: User) -> User:
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _mentor(settings: Settings) -> tuple[Mentor, dict[str, str]]:
    user = await _approved(await create_user())
    return await create_mentor(user), bearer(settings, user)


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


def _at(days: int, hour: int) -> datetime:
    day = datetime.now(KST).date() + timedelta(days=days)
    return datetime(day.year, day.month, day.day, hour, tzinfo=KST)


async def test_mentor_manages_unavailable_periods(client: AsyncClient, settings: Settings) -> None:
    _, h = await _mentor(settings)
    work = await client.post(
        f"{ME}/unavailable-periods",
        json={
            "repeat": "WEEKLY",
            "weekdays": [1, 2, 3, 4, 5],
            "starts_at": _at(-7, 9).isoformat(),  # 이미 시작된 반복도 된다
            "ends_at": _at(-7, 18).isoformat(),
            "category": "근무",
        },
        headers=h,
    )
    assert work.status_code == 201, work.text
    body = work.json()
    assert (body["applied"], body["conflicts"]) == (True, [])
    assert body["unavailable_period"]["weekdays"] == [1, 2, 3, 4, 5]
    work_id = body["unavailable_period"]["id"]

    sleep = await client.post(
        f"{ME}/unavailable-periods",
        json={
            "repeat": "DAILY",
            "starts_at": _at(1, 23).isoformat(),
            "ends_at": _at(2, 7).isoformat(),  # 자정 넘김
        },
        headers=h,
    )
    assert sleep.status_code == 201, sleep.text
    day = (datetime.now(KST) + timedelta(days=10)).date()
    vacation = await client.post(
        f"{ME}/unavailable-periods",
        json={"all_day": True, "start_date": str(day), "end_date": str(day), "reason": "휴가"},
        headers=h,
    )
    assert vacation.json()["unavailable_period"]["all_day"] is True
    vacation_id = vacation.json()["unavailable_period"]["id"]

    for bad in (
        {"repeat": "WEEKLY", "starts_at": _at(1, 9).isoformat(), "ends_at": _at(1, 18).isoformat()},
        {"repeat": "DAILY", "starts_at": _at(1, 9).isoformat(), "ends_at": _at(2, 10).isoformat()},
        {"starts_at": _at(-1, 9).isoformat(), "ends_at": _at(-1, 10).isoformat()},
    ):
        response = await client.post(f"{ME}/unavailable-periods", json=bad, headers=h)
        assert response.status_code == 422, bad
    assert (
        await client.post(
            f"{ME}/unavailable-periods",
            json={"repeat": "DAILY", "all_day": True, "start_date": str(day), "end_date": str(day)},
            headers=h,
        )
    ).status_code == 422

    changed = await client.put(
        f"{ME}/unavailable-periods/{work_id}",
        json={
            "repeat": "WEEKLY",
            "weekdays": [1, 3, 5],
            "starts_at": _at(-7, 9).isoformat(),
            "ends_at": _at(-7, 17).isoformat(),
            "repeat_until": str(day),
            "category": "근무",
        },
        headers=h,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["unavailable_period"]["weekdays"] == [1, 3, 5]

    schedule = (await client.get(ME, headers=h)).json()
    assert schedule["accepting_requests"] is False
    assert len(schedule["unavailable_periods"]) == 3
    assert (
        await client.delete(f"{ME}/unavailable-periods/{vacation_id}", headers=h)
    ).status_code == 204
    assert len((await client.get(ME, headers=h)).json()["unavailable_periods"]) == 2


async def test_accepting_switch(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    mentor, h = await _mentor(settings)
    on = await client.put(f"{ME}/accepting", json={"accepting_requests": True}, headers=h)
    assert on.json() == {"mentor_id": str(mentor.id), "accepting_requests": True}
    assert (await client.get(ME, headers=h)).json()["accepting_requests"] is True

    await client.post(
        f"/api/v1/admin/mentors/{mentor.id}/deactivate", json={"confirm": True}, headers=admin
    )
    assert (await client.get(ME, headers=h)).json()["accepting_requests"] is False
    blocked = await client.put(f"{ME}/accepting", json={"accepting_requests": True}, headers=h)
    assert blocked.json()["error"]["code"] == "mentor_inactive"
    period = await client.post(
        f"{ME}/unavailable-periods",
        json={"starts_at": _at(3, 9).isoformat(), "ends_at": _at(3, 10).isoformat()},
        headers=h,
    )
    assert period.json()["error"]["code"] == "mentor_inactive"


async def test_admin_proxy_and_permissions(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    mentor, _ = await _mentor(settings)
    base = f"/api/v1/admin/mentors/{mentor.id}/schedule"
    created = await client.post(
        f"{base}/unavailable-periods",
        json={"starts_at": _at(3, 9).isoformat(), "ends_at": _at(3, 10).isoformat()},
        headers=admin,
    )
    assert created.status_code == 201
    accepting = await client.put(
        f"{base}/accepting", json={"accepting_requests": True}, headers=admin
    )
    assert accepting.json()["accepting_requests"] is True
    assert len((await client.get(base, headers=admin)).json()["unavailable_periods"]) == 1

    await seed_roles()
    assistant_user = await _approved(await create_applicant())
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        assistant_user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, (await create_cohort()).id
    )
    assert (await client.get(base, headers=bearer(settings, assistant_user))).status_code == 403
    assert (await client.get(base)).status_code == 401
    stranger = bearer(settings, await _approved(await create_user()))
    missing = await client.get(ME, headers=stranger)
    assert missing.json()["error"]["code"] == "mentor_profile_not_found"


async def test_cohort_operating_hours(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    path = f"/api/v1/admin/cohorts/{cohort.id}/mentoring-settings"
    base = {"allow_1_on_1": True}
    defaults = await client.put(path, json=base, headers=admin)
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["weekday_hours"] == {"start": "10:00", "end": "19:00"}
    assert defaults.json()["weekend_hours"] is None

    custom = await client.put(
        path,
        json={**base, "weekday_hours": None, "weekend_hours": {"start": "13:00", "end": "24:00"}},
        headers=admin,
    )
    assert custom.json()["weekday_hours"] is None
    assert custom.json()["weekend_hours"] == {"start": "13:00", "end": "24:00"}
    assert (await client.get(path, headers=admin)).json()["weekend_hours"]["end"] == "24:00"

    bad = await client.put(
        path, json={**base, "weekday_hours": {"start": "10:15", "end": "19:00"}}, headers=admin
    )
    assert bad.json()["error"]["code"] == "invalid_operating_hours"

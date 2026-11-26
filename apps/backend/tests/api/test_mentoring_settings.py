"""기수 멘토링 설정·금지 시간대·추가 휴일 API (실제 DB)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import ASSISTANT, MANAGER, give_role
from tests.factories.educator import create_mentor, create_user
from tests.factories.staff_review import create_applicant

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
async def http_client(app: FastAPI) -> AsyncIterator[None]:
    """lifespan을 돌리지 않으므로 공휴일 동기화가 쓰는 공유 클라이언트를 직접 둔다."""
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _staff(settings: Settings, role: str, cohort_id: object) -> dict[str, str]:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await give_role(user.id, role, cohort_id=cohort_id)  # type: ignore[arg-type]
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


@pytest.mark.usefixtures("http_client")
async def test_holidays(client: AsyncClient, admin: dict[str, str], app: FastAPI) -> None:
    app.state.clock = FixedClock(datetime(2026, 11, 25, 3, 0, tzinfo=UTC))
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

    before = (
        await client.get(f"{API}/mentoring-holidays", params={"year": 2026}, headers=admin)
    ).json()
    assert before["synced_at"] is None  # 아직 받지 않은 해 (A95)
    assert [(h["holiday_date"], h["source"]) for h in before["items"]] == [("2026-11-20", "CUSTOM")]

    synced = await client.post(f"{API}/mentoring-holidays/sync", headers=admin)
    assert synced.status_code == 200
    years = synced.json()["years"]
    assert [y["year"] for y in years] == [2026, 2027]  # 테스트 시계 기준 올해·내년
    assert years[0]["holiday_count"] == 22

    listed = (
        await client.get(f"{API}/mentoring-holidays", params={"year": 2026}, headers=admin)
    ).json()
    assert listed["synced_at"] is not None
    sources = {(h["holiday_date"], h["source"]) for h in listed["items"]}
    assert ("2026-11-20", "CUSTOM") in sources
    assert ("2026-09-25", "PUBLIC") in sources  # 추석

    deleted = await client.delete(f"{API}/mentoring-holidays/{created.json()['id']}", headers=admin)
    assert deleted.status_code == 204


async def test_permissions(client: AsyncClient, settings: Settings) -> None:
    mine, other = await create_cohort(), await create_cohort()
    manager = await _staff(settings, MANAGER, mine.id)
    assistant = await _staff(settings, ASSISTANT, mine.id)

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
    assert (
        await client.post(f"{API}/mentoring-holidays/sync", headers=assistant)
    ).status_code == 403


@pytest.mark.usefixtures("http_client")
async def test_sync_unconfigured_is_503(
    client: AsyncClient, admin: dict[str, str], app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"holiday_driver": "data_go_kr"})
    response = await client.post(f"{API}/mentoring-holidays/sync", headers=admin)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "holiday_sync_failed"


@pytest.mark.usefixtures("http_client")
async def test_calendar_holidays_for_any_signed_in_user(
    client: AsyncClient, admin: dict[str, str], settings: Settings, app: FastAPI
) -> None:
    """달력 참고용 휴일 (A107): 멘토도 기간으로 법정공휴일·추가 휴일을 받는다."""
    app.state.clock = FixedClock(datetime(2026, 11, 25, 3, 0, tzinfo=UTC))
    await client.post(
        f"{API}/mentoring-holidays",
        json={"holiday_date": "2026-12-24", "name": "학원 휴무"},
        headers=admin,
    )
    synced = await client.post(f"{API}/mentoring-holidays/sync", headers=admin)
    assert synced.status_code == 200, synced.text
    user = await create_user()
    await create_mentor(user)
    headers = bearer(settings, user)

    url = "/api/v1/mentoring/holidays"
    listed = await client.get(
        url, params={"from": "2026-12-01", "to": "2026-12-31"}, headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["items"] == [
        {"holiday_date": "2026-12-24", "name": "학원 휴무", "source": "CUSTOM"},
        {"holiday_date": "2026-12-25", "name": "기독탄신일", "source": "PUBLIC"},
    ]

    too_long = await client.get(
        url, params={"from": "2026-01-01", "to": "2026-12-31"}, headers=headers
    )
    assert too_long.json()["error"]["code"] == "invalid_holiday_range"
    reversed_ = await client.get(
        url, params={"from": "2026-12-31", "to": "2026-12-01"}, headers=headers
    )
    assert reversed_.status_code == 422
    assert (
        await client.get(url, params={"from": "2026-12-01", "to": "2026-12-31"})
    ).status_code == 401

"""신청 가능 시간 조회 API (실제 DB, A37)."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.time import KST
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_mentor_contract, create_user

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved() -> User:
    user = await create_user()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def test_student_sees_available_times(client: AsyncClient, settings: Settings) -> None:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    today = datetime.now(KST).date()
    mentor_user = await _approved()
    mentor = await create_mentor(mentor_user)
    await client.post(
        f"{api}/mentor-assignments",
        json={
            "mentor_id": str(mentor.id),
            "start_date": "2026-11-01",
            "contract_id": str(
                (
                    await create_mentor_contract(
                        mentor.id, bootcamp_id=cohort.bootcamp_id, cohort_id=cohort.id
                    )
                ).id
            ),
        },
        headers=admin,
    )
    student_user = await _approved()
    await TortoiseStudentRepository().add(
        make_student(cohort_id=cohort.id, user_id=student_user.id)
    )
    student = bearer(settings, student_user)
    start, end = today + timedelta(days=7), today + timedelta(days=13)
    url = f"/api/v1/mentors/{mentor.id}/available-times"
    params = {"cohort_id": str(cohort.id), "from": str(start), "to": str(end)}

    missing = await client.get(url, params=params, headers=student)
    assert missing.json()["error"]["code"] == "mentoring_settings_not_configured"
    weekend = {"start": "10:00", "end": "19:00"}
    await client.put(
        f"{api}/mentoring-settings",
        json={"allow_1_on_1": True, "weekend_hours": weekend},
        headers=admin,
    )

    closed = (await client.get(url, params=params, headers=student)).json()
    assert (closed["accepting_requests"], closed["intervals"]) == (False, [])

    mentor_h = bearer(settings, mentor_user)
    await client.put(
        "/api/v1/me/mentor-schedule/accepting", json={"accepting_requests": True}, headers=mentor_h
    )
    lunch_start = datetime.combine(today, datetime.min.time(), KST).replace(hour=12)
    await client.post(
        "/api/v1/me/mentor-schedule/unavailable-periods",
        json={
            "repeat": "DAILY",
            "starts_at": lunch_start.isoformat(),
            "ends_at": (lunch_start + timedelta(hours=1)).isoformat(),
        },
        headers=mentor_h,
    )

    body = (await client.get(url, params=params, headers=student)).json()
    assert body["accepting_requests"] is True
    assert (body["allowed_duration"], body["min_lead_hours"]) == (30, 24)
    intervals = [
        (
            datetime.fromisoformat(i["starts_at"]).astimezone(KST),
            datetime.fromisoformat(i["ends_at"]).astimezone(KST),
        )
        for i in body["intervals"]
    ]
    # 7일 × (10~12시, 13~19시) — 주말도 같은 운영시간으로 열었다
    assert len(intervals) == 14
    for begin, finish in intervals:
        assert begin.date() == finish.date()
        assert (begin.hour, finish.hour) in {(10, 12), (13, 19)}

    # 멘토 본인·운영진은 보고, 다른 회원은 403
    assert (await client.get(url, params=params, headers=mentor_h)).status_code == 200
    assert (await client.get(url, params=params, headers=admin)).status_code == 200
    stranger = bearer(settings, await _approved())
    assert (await client.get(url, params=params, headers=stranger)).status_code == 403
    assert (await client.get(url, params=params)).status_code == 401
    too_long = {**params, "to": str(start + timedelta(days=31))}
    assert (await client.get(url, params=too_long, headers=student)).json()["error"]["code"] == (
        "invalid_time_range"
    )

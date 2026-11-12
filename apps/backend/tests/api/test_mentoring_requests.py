"""멘토링 신청 API (실제 DB, A42 P11-1: 신청·승인 전 취소·조회)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from app.shared.time import KST
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user

pytestmark = pytest.mark.api

URL = "/api/v1/mentoring/requests"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved(name: str = "회원") -> User:
    user = await create_user(name=name)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _setup(client: AsyncClient, settings: Settings) -> dict[str, Any]:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    hours = {"start": "10:00", "end": "19:00"}
    await client.put(
        f"{api}/mentoring-settings",
        json={
            "allow_1_on_1": True,
            "default_1on1_minutes": 180,
            "max_pending_requests": 3,
            "weekday_hours": hours,
            "weekend_hours": hours,
        },
        headers=admin,
    )
    mentor_user = await _approved("김멘토")
    mentor = await create_mentor(mentor_user)
    await client.post(
        f"{api}/mentor-assignments",
        json={
            "mentor_id": str(mentor.id),
            "start_date": "2026-11-01",
            "cost_settlement_policy": "ACTUAL_DURATION",
            "pay_unit": "HOURLY",
            "pay_rate": 30000,
        },
        headers=admin,
    )
    mentor_h = bearer(settings, mentor_user)
    await client.put(
        "/api/v1/me/mentor-schedule/accepting", json={"accepting_requests": True}, headers=mentor_h
    )
    student_user = await _approved()
    student = make_student(cohort_id=cohort.id, name="가수강", user_id=student_user.id)
    await TortoiseStudentRepository().add(student)
    granted = await client.post(
        f"{api}/mentoring-balances/grants",
        json={"target": "ALL_STUDENTS", "reason": "기본 지급"},
        headers={**admin, "Idempotency-Key": str(new_id())},
    )
    assert granted.status_code == 200, granted.text
    day = datetime.now(KST).date() + timedelta(days=7)
    return {
        "admin": admin,
        "admin_path": f"{api}/mentoring/requests",
        "cohort": cohort,
        "mentor": mentor,
        "mentor_h": mentor_h,
        "student_h": bearer(settings, student_user),
        "at": datetime.combine(day, datetime.min.time(), KST).replace(hour=14),
    }


def _body(ctx: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cohort_id": str(ctx["cohort"].id),
        "mentor_id": str(ctx["mentor"].id),
        "topic": "포트폴리오 리뷰",
        "detail": "구조를 봐 주세요",
        "desired_times": [ctx["at"].isoformat()],
        "duration": 60,
    }
    body.update(overrides)
    return body


async def test_create_cancel_and_lists(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    student_h = ctx["student_h"]

    created = await client.post(URL, json=_body(ctx), headers=student_h)
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["status"], body["requester_name"], body["team_id"]) == ("PENDING", "가수강", None)
    assert body["mentor_display_name"]
    assert "mentor_name" not in body  # 수강생 응답엔 멘토 실명 없음
    balances = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert [(a["remaining_minutes"], a["held_minutes"]) for a in balances] == [(120, 60)]

    mine = (await client.get("/api/v1/me/mentoring/requests", headers=student_h)).json()
    assert [r["id"] for r in mine["items"]] == [body["id"]]
    received = (
        await client.get(
            "/api/v1/me/mentor-requests", params={"status": "PENDING"}, headers=ctx["mentor_h"]
        )
    ).json()
    assert received["total"] == 1
    staff = (await client.get(ctx["admin_path"], headers=ctx["admin"])).json()
    assert staff["items"][0]["mentor_name"] == "김멘토"

    no_reason = await client.post(
        f"{URL}/{body['id']}/cancel", json={"reason": ""}, headers=student_h
    )
    assert no_reason.status_code == 422
    other = await client.post(
        f"{URL}/{body['id']}/cancel", json={"reason": "남의 신청"}, headers=ctx["mentor_h"]
    )
    assert other.status_code == 403
    canceled = await client.post(
        f"{URL}/{body['id']}/cancel", json={"reason": "일정 변경"}, headers=student_h
    )
    assert (canceled.json()["status"], canceled.json()["cancel_reason"]) == (
        "CANCELED",
        "일정 변경",
    )
    balances = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert [(a["remaining_minutes"], a["held_minutes"]) for a in balances] == [(180, 0)]
    filtered = (
        await client.get(ctx["admin_path"], params={"status": "PENDING"}, headers=ctx["admin"])
    ).json()
    assert filtered["total"] == 0


async def test_create_rules_and_permissions(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    student_h = ctx["student_h"]
    off_hours = ctx["at"].replace(hour=9)
    unavailable = await client.post(
        URL, json=_body(ctx, desired_times=[off_hours.isoformat()]), headers=student_h
    )
    assert unavailable.json()["error"]["code"] == "desired_time_unavailable"
    too_long = await client.post(URL, json=_body(ctx, duration=150), headers=student_h)
    assert too_long.status_code == 422
    over = await client.post(
        URL, json=_body(ctx, duration=120, desired_times=[ctx["at"].isoformat()]), headers=student_h
    )
    assert over.status_code == 201
    insufficient = await client.post(URL, json=_body(ctx, duration=120), headers=student_h)
    assert insufficient.json()["error"]["code"] == "insufficient_balance"
    no_target = await client.post(
        URL, json=_body(ctx, cohort_id=None, mentor_id=None), headers=student_h
    )
    assert no_target.json()["error"]["code"] == "request_target_required"

    stranger = bearer(settings, await _approved())
    assert (await client.post(URL, json=_body(ctx), headers=stranger)).status_code == 403
    assert (await client.post(URL, json=_body(ctx))).status_code == 401
    assert (await client.get(ctx["admin_path"], headers=student_h)).status_code == 403
    not_mentor = await client.get("/api/v1/me/mentor-requests", headers=student_h)
    assert not_mentor.status_code == 404

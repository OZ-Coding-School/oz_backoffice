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


async def test_approve_reject_and_sessions(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    second = ctx["at"] + timedelta(hours=2)
    request_id = (
        await client.post(
            URL,
            json=_body(ctx, desired_times=[ctx["at"].isoformat(), second.isoformat()]),
            headers=student_h,
        )
    ).json()["id"]
    approve = f"{URL}/{request_id}/approve"

    assert (
        await client.post(approve, json={"starts_at": second.isoformat()}, headers=student_h)
    ).status_code == 404  # 멘토 프로필 없음
    not_desired = await client.post(
        approve, json={"starts_at": (second + timedelta(hours=1)).isoformat()}, headers=mentor_h
    )
    assert not_desired.json()["error"]["code"] == "not_desired_time"
    approved = await client.post(approve, json={"starts_at": second.isoformat()}, headers=mentor_h)
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["request"]["status"] == "APPROVED"
    session = body["session"]
    assert session["status"] == "SCHEDULED"
    assert session["title"].startswith("가수강 · ")
    assert session["title"].endswith("멘토링 1회차")
    assert datetime.fromisoformat(session["starts_at"]) == second
    assert session["google_meet_url"] is None
    assert "mentor_name" not in session
    balances = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert [(a["remaining_minutes"], a["held_minutes"]) for a in balances] == [(120, 0)]
    again = await client.post(approve, json={"starts_at": second.isoformat()}, headers=mentor_h)
    assert again.json()["error"]["code"] == "request_not_pending"

    # 반려
    other_id = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    no_reason = await client.post(f"{URL}/{other_id}/reject", json={"reason": ""}, headers=mentor_h)
    assert no_reason.status_code == 422
    rejected = await client.post(
        f"{URL}/{other_id}/reject", json={"reason": "일정이 맞지 않음"}, headers=mentor_h
    )
    assert (rejected.json()["status"], rejected.json()["reject_reason"]) == (
        "REJECTED",
        "일정이 맞지 않음",
    )

    # 세션 조회
    mine = (await client.get("/api/v1/me/mentoring/sessions", headers=student_h)).json()
    assert [s["id"] for s in mine["items"]] == [session["id"]]
    mentor_list = await client.get(
        "/api/v1/me/mentor-sessions", params={"status": "SCHEDULED"}, headers=mentor_h
    )
    assert mentor_list.json()["total"] == 1
    window = await client.get(
        "/api/v1/me/mentoring/sessions",
        params={"from": ctx["at"].isoformat(), "to": second.isoformat()},
        headers=student_h,
    )
    assert window.json()["total"] == 0  # 시작 시각이 to와 같으면 제외
    detail = await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=student_h)
    assert detail.json()["detail"] == "구조를 봐 주세요"
    stranger = bearer(settings, await _approved())
    hidden = await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=stranger)
    assert hidden.status_code == 404

    admin_path = f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring/sessions"
    staff = (await client.get(admin_path, headers=admin)).json()
    assert staff["items"][0]["mentor_name"] == "김멘토"
    one = await client.get(f"{admin_path}/{session['id']}", headers=admin)
    assert one.json()["id"] == session["id"]
    elsewhere = await create_cohort()
    wrong = await client.get(
        f"/api/v1/admin/cohorts/{elsewhere.id}/mentoring/sessions/{session['id']}", headers=admin
    )
    assert wrong.status_code == 404
    assert (await client.get(admin_path, headers=student_h)).status_code == 403
    assert (await client.get(admin_path)).status_code == 401


async def test_cancel_change_and_staff_cancel(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    at = ctx["at"]

    async def balance() -> tuple[int, int, int]:
        (a,) = (await client.get("/api/v1/me/balances", headers=student_h)).json()
        return a["remaining_minutes"], a["held_minutes"], a["used_minutes"]

    first = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    approved = await client.post(
        f"{URL}/{first}/approve", json={"starts_at": at.isoformat()}, headers=mentor_h
    )
    session_id = approved.json()["session"]["id"]
    assert await balance() == (120, 0, 60)

    # 잡힌 세션은 신청 가능 시간에서 빠진다
    times = await client.get(
        f"/api/v1/mentors/{ctx['mentor'].id}/available-times",
        params={"cohort_id": str(ctx["cohort"].id), "from": str(at.date()), "to": str(at.date())},
        headers=student_h,
    )
    spans = [
        (datetime.fromisoformat(i["starts_at"]), datetime.fromisoformat(i["ends_at"]))
        for i in times.json()["intervals"]
    ]
    assert not any(s < at + timedelta(hours=1) and at < e for s, e in spans)

    later = at + timedelta(hours=2)
    second = (
        await client.post(
            URL, json=_body(ctx, desired_times=[later.isoformat()], duration=120), headers=student_h
        )
    ).json()["id"]
    assert await balance() == (0, 120, 60)

    # 새 신청이 트랜잭션 안에서 실패하면(잔여 부족) 기존 신청 취소도 되돌린다
    change = {"topic": "새 주제", "detail": "새 내용", "desired_times": [at.isoformat()]}
    failed = await client.post(
        f"{URL}/{first}/change", json={**change, "duration": 120}, headers=student_h
    )
    assert failed.json()["error"]["code"] == "insufficient_balance"
    session = await client.get(f"/api/v1/mentoring/sessions/{session_id}", headers=student_h)
    assert session.json()["status"] == "SCHEDULED"
    assert await balance() == (0, 120, 60)

    await client.post(f"{URL}/{second}/cancel", json={"reason": "필요 없음"}, headers=student_h)
    assert (
        await client.post(
            f"{URL}/{first}/change", json={**change, "duration": 30}, headers=mentor_h
        )
    ).status_code == 403
    changed = await client.post(
        f"{URL}/{first}/change", json={**change, "duration": 30}, headers=student_h
    )
    assert changed.status_code == 201, changed.text
    new = changed.json()
    assert (new["replaced_request_id"], new["status"], new["duration"]) == (first, "PENDING", 30)
    assert await balance() == (150, 30, 0)
    session = await client.get(f"/api/v1/mentoring/sessions/{session_id}", headers=student_h)
    assert session.json()["status"] == "CANCELED"

    # 운영진 취소: 승인된 신청, 환불 안 함 → 사용 유지
    await client.post(
        f"{URL}/{new['id']}/approve", json={"starts_at": at.isoformat()}, headers=mentor_h
    )
    staff_path = f"{ctx['admin_path']}/{new['id']}/cancel"
    assert (
        await client.post(staff_path, json={"reason": "정리"}, headers=student_h)
    ).status_code == 403
    staff = await client.post(
        staff_path, json={"reason": "운영 정리", "refund": False}, headers=admin
    )
    assert staff.status_code == 200, staff.text
    assert (staff.json()["status"], staff.json()["cancel_reason"]) == ("CANCELED", "운영 정리")
    assert await balance() == (150, 0, 30)
    again = await client.post(staff_path, json={"reason": "다시"}, headers=admin)
    assert again.json()["error"]["code"] == "request_not_cancelable"


async def test_mentor_changes_cancel_pending(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    first = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    off = await client.put(
        "/api/v1/me/mentor-schedule/accepting", json={"accepting_requests": False}, headers=mentor_h
    )
    assert off.json()["canceled_pending_requests"] == 1
    mine = (await client.get("/api/v1/me/mentoring/requests", headers=student_h)).json()
    assert {r["id"]: r["status"] for r in mine["items"]} == {first: "CANCELED"}
    (balance,) = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert (balance["remaining_minutes"], balance["held_minutes"]) == (180, 0)

    await client.put(
        "/api/v1/me/mentor-schedule/accepting", json={"accepting_requests": True}, headers=mentor_h
    )
    second = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    api = f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentor-assignments"
    (assignment,) = (await client.get(api, headers=admin)).json()
    removed = await client.delete(f"{api}/{assignment['id']}", headers=admin)
    assert (removed.json()["is_active"], removed.json()["canceled_pending_requests"]) == (False, 1)
    mine = (await client.get("/api/v1/me/mentoring/requests", headers=student_h)).json()
    assert {r["id"]: r["status"] for r in mine["items"]}[second] == "CANCELED"


async def test_unavailable_conflicts_reject_and_cancel(
    client: AsyncClient, settings: Settings
) -> None:
    ctx = await _setup(client, settings)
    student_h, mentor_h = ctx["student_h"], ctx["mentor_h"]
    at = ctx["at"]
    pending = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    later = at + timedelta(hours=2)
    approved = (
        await client.post(
            URL, json=_body(ctx, desired_times=[later.isoformat()]), headers=student_h
        )
    ).json()["id"]
    session = (
        await client.post(
            f"{URL}/{approved}/approve", json={"starts_at": later.isoformat()}, headers=mentor_h
        )
    ).json()["session"]
    path = "/api/v1/me/mentor-schedule/unavailable-periods"
    body = {"starts_at": at.isoformat(), "ends_at": (at + timedelta(hours=4)).isoformat()}

    preview = await client.post(path, json=body, headers=mentor_h)
    assert preview.json()["applied"] is False
    assert {(c["kind"], c["target_id"]) for c in preview.json()["conflicts"]} == {
        ("REQUEST", pending),
        ("SESSION", session["id"]),
    }
    done = await client.post(path, params={"confirm": "true"}, json=body, headers=mentor_h)
    assert done.json()["applied"] is True

    mine = (await client.get("/api/v1/me/mentoring/requests", headers=student_h)).json()
    statuses = {r["id"]: (r["status"], r["reject_reason"]) for r in mine["items"]}
    assert statuses[pending] == ("REJECTED", "멘토 일정 변경")
    assert statuses[approved][0] == "CANCELED"
    shown = await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=student_h)
    assert shown.json()["status"] == "CANCELED"
    (balance,) = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert (balance["remaining_minutes"], balance["held_minutes"], balance["used_minutes"]) == (
        180,
        0,
        0,
    )


async def test_meet_link_shown_then_hidden_after_cancel(
    client: AsyncClient, settings: Settings
) -> None:
    from app.contexts.mentoring.application.meet_service import MeetSpaceService
    from app.contexts.mentoring.infrastructure.repositories import (
        TortoiseMentoringSessionRepository,
    )
    from app.core.clock import SystemClock
    from app.core.uow import UnitOfWork
    from tests.fakes.mentoring import FakeMeetClient

    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    request_id = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    session = (
        await client.post(
            f"{URL}/{request_id}/approve",
            json={"starts_at": ctx["at"].isoformat()},
            headers=mentor_h,
        )
    ).json()["session"]
    assert session["google_meet_url"] is None  # 공간은 커밋 후 작업이 만든다

    meet = FakeMeetClient()
    service = MeetSpaceService(
        sessions=TortoiseMentoringSessionRepository(),
        meet=meet,
        uow=UnitOfWork(),
        clock=SystemClock(),
    )
    assert await service.sync() == (1, 0)
    shown = (
        await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=student_h)
    ).json()
    assert shown["google_meet_url"] == "https://meet.google.com/s1"

    await client.post(
        f"{ctx['admin_path']}/{request_id}/cancel", json={"reason": "정리"}, headers=admin
    )
    hidden = (
        await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=student_h)
    ).json()
    assert hidden["google_meet_url"] is None  # 취소되면 바로 숨긴다
    assert await service.sync() == (0, 1)
    assert meet.restricted == ["spaces/s1"]

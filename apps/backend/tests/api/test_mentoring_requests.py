"""멘토링 신청 API (실제 DB, A42 P11-1: 신청·승인 전 취소·조회)."""

import uuid
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
    mentor = await create_mentor(mentor_user, headline="백엔드 10년차")
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
        "student": student,
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
    # 신청자 기수·수강 상태 (A76)
    item = received["items"][0]
    assert item["cohort_id"] == str(ctx["cohort"].id)
    assert (item["cohort_number"], item["requester_status"]) == (
        ctx["cohort"].cohort_number,
        "ENROLLED",
    )
    assert item["bootcamp_name"]
    for cohort_id, total in ((ctx["cohort"].id, 1), (new_id(), 0)):  # 기수 필터·건수 (A76)
        filtered = (
            await client.get(
                "/api/v1/me/mentor-requests",
                params={"cohort_id": str(cohort_id)},
                headers=ctx["mentor_h"],
            )
        ).json()
        assert (filtered["total"], filtered["counts"]["PENDING"]) == (total, total)
    staff = (await client.get(ctx["admin_path"], headers=ctx["admin"])).json()
    assert staff["items"][0]["mentor_name"] == "김멘토"
    for params, total in (  # 신청자 1:1만 / 팀만 (A59)
        ({"student_id": str(ctx["student"].id)}, 1),
        ({"student_id": str(new_id())}, 0),
        ({"team_id": str(new_id())}, 0),
    ):
        filtered = await client.get(ctx["admin_path"], params=params, headers=ctx["admin"])
        assert filtered.json()["total"] == total

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


async def test_request_detail_and_supplement_fields(
    client: AsyncClient, settings: Settings
) -> None:
    """단건 조회 권한과 확정 세션·한 줄 소개·취소 주체·차감 상태 (A66)."""
    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    request_id = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    detail = f"{URL}/{request_id}"

    pending = (await client.get(detail, headers=student_h)).json()
    assert (
        pending["mentor_headline"],
        pending["session"],
        pending["canceled_by"],
        pending["balance"],
    ) == ("백엔드 10년차", None, None, {"state": "HELD", "minutes": 60})
    assert "mentor_name" not in pending
    assert (await client.get(detail, headers=mentor_h)).json()["id"] == request_id
    stranger = await client.get(detail, headers=bearer(settings, await _approved()))
    assert (stranger.status_code, stranger.json()["error"]["code"]) == (404, "request_not_found")
    assert (await client.get(f"{URL}/{new_id()}", headers=student_h)).status_code == 404
    assert (await client.get(detail)).status_code == 401

    approved = await client.post(
        f"{detail}/approve", json={"starts_at": ctx["at"].isoformat()}, headers=mentor_h
    )
    session = approved.json()["session"]
    after = (await client.get(detail, headers=student_h)).json()
    assert after["session"]["id"] == session["id"]
    assert datetime.fromisoformat(after["session"]["starts_at"]) == ctx["at"]
    assert datetime.fromisoformat(after["session"]["ends_at"]) == ctx["at"] + timedelta(hours=1)
    assert after["balance"] == {"state": "USED", "minutes": 60}

    staff = await client.post(
        f"{ctx['admin_path']}/{request_id}/cancel",
        json={"reason": "운영 정리", "refund": True},
        headers=admin,
    )
    body = staff.json()
    assert (body["canceled_by"], body["balance"], body["session"]) == (
        "STAFF",
        {"state": "RETURNED", "minutes": 60},
        None,  # 취소된 신청에는 확정 세션이 없다
    )
    mine = (await client.get("/api/v1/me/mentoring/requests", headers=student_h)).json()
    assert mine["items"][0]["canceled_by"] == "STAFF"

    other = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    canceled = await client.post(
        f"{URL}/{other}/cancel", json={"reason": "일정 변경"}, headers=student_h
    )
    assert (canceled.json()["canceled_by"], canceled.json()["balance"]) == (
        "REQUESTER",
        {"state": "RETURNED", "minutes": 60},
    )

    # 상태 여러 개 필터와 상태별 건수 (A67)
    waiting = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    counts = {"PENDING": 1, "APPROVED": 0, "REJECTED": 0, "CANCELED": 2}
    closed = await client.get(
        "/api/v1/me/mentoring/requests",
        params=[("status", "REJECTED"), ("status", "CANCELED")],
        headers=student_h,
    )
    body = closed.json()
    assert ({r["id"] for r in body["items"]}, body["total"], body["counts"]) == (
        {request_id, other},
        2,
        counts,
    )
    received = await client.get(
        "/api/v1/me/mentor-requests", params={"status": "PENDING"}, headers=mentor_h
    )
    assert ([r["id"] for r in received.json()["items"]], received.json()["counts"]) == (
        [waiting],
        counts,
    )
    wrong = await client.get(
        "/api/v1/me/mentoring/requests", params={"status": "DONE"}, headers=student_h
    )
    assert wrong.status_code == 422


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
    assert mine["counts"] == {  # 상태별 세션 수 (A68)
        "SCHEDULED": 1,
        "IN_PROGRESS": 0,
        "COMPLETED": 0,
        "NO_SHOW": 0,
        "CANCELED": 0,
    }
    for statuses, total in (  # 상태 여러 개 (A70)
        ({"status": ["SCHEDULED", "IN_PROGRESS"]}, 1),
        ({"status": ["COMPLETED", "NO_SHOW"]}, 0),
    ):
        filtered = await client.get(
            "/api/v1/me/mentoring/sessions", params=statuses, headers=student_h
        )
        assert filtered.json()["total"] == total
    mentor_list = await client.get(
        "/api/v1/me/mentor-sessions", params={"status": "SCHEDULED"}, headers=mentor_h
    )
    assert mentor_list.json()["total"] == 1
    assert mentor_list.json()["counts"]["SCHEDULED"] == 1
    # 탭별 수·기수 (A77)
    assert mentor_list.json()["view_counts"]["all"] == 1
    assert mentor_list.json()["items"][0]["cohort_number"] == ctx["cohort"].cohort_number
    past_view = await client.get(
        "/api/v1/me/mentor-sessions", params={"view": "past"}, headers=mentor_h
    )
    assert (past_view.json()["total"], past_view.json()["view_counts"]["past"]) == (0, 0)
    other_cohort = await client.get(
        "/api/v1/me/mentor-sessions", params={"cohort_id": str(new_id())}, headers=mentor_h
    )
    assert (other_cohort.json()["total"], other_cohort.json()["view_counts"]["all"]) == (0, 0)
    bad_view = await client.get(
        "/api/v1/me/mentor-sessions", params={"view": "later"}, headers=mentor_h
    )
    assert bad_view.status_code == 422
    for order, code in (("asc", 200), ("desc", 200), ("oldest", 422)):  # 정렬 (A75)
        ordered = await client.get(
            "/api/v1/me/mentoring/sessions", params={"order": order}, headers=student_h
        )
        assert ordered.status_code == code
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
    for params, total in (  # 신청자 1:1만 / 팀만 (A59)
        ({"student_id": str(ctx["student"].id)}, 1),
        ({"team_id": str(new_id())}, 0),
    ):
        filtered = await client.get(admin_path, params=params, headers=admin)
        assert filtered.json()["total"] == total
    one = await client.get(f"{admin_path}/{session['id']}", headers=admin)
    assert one.json()["id"] == session["id"]
    assert one.json()["uncharged_overtime_minutes"] is None  # 운영진만 본다 (A78)
    assert "uncharged_overtime_minutes" not in detail.json()
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
    # 취소된 세션에도 신청의 취소 사유·주체·차감 상태가 보인다 (A68: 변경은 신청자 취소)
    canceled = session.json()
    assert (canceled["canceled_by"], canceled["balance"]["state"]) == ("REQUESTER", "RETURNED")
    assert canceled["cancel_reason"]
    assert canceled["canceled_at"]

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
    # 주제·신청자 (A79)
    assert {(c["topic"], c["requester_label"]) for c in preview.json()["conflicts"]} == {
        (_body(ctx)["topic"], "가수강")
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
    from app.contexts.educator.application.mentor_queries import MentorQueries
    from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
    from app.contexts.identity.application.auth_service import UserQueries
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
        mentors=MentorQueries(TortoiseMentorRepository()),
        users=UserQueries(TortoiseUserRepository()),
        uow=UnitOfWork(),
        clock=SystemClock(),
    )
    assert await service.sync() == (1, 0)
    assert len(meet.cohosts) == 1  # 담당 멘토의 가입 이메일이 공동 주최자 (A52)
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


async def test_record_note_and_unrecorded(
    app: Any, client: AsyncClient, settings: Settings
) -> None:
    from app.core.clock import FixedClock

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
    record = f"/api/v1/mentoring/sessions/{session['id']}/record"
    admin_sessions = f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring/sessions"

    early = await client.post(
        record, json={"status": "COMPLETED", "duration": 60, "summary": "요약"}, headers=mentor_h
    )
    assert early.json()["error"]["code"] == "session_not_started"

    app.state.clock = FixedClock(ctx["at"] + timedelta(hours=1))  # 진행 후
    unrecorded = (await client.get(f"{admin_sessions}/unrecorded", headers=admin)).json()
    assert [s["id"] for s in unrecorded["items"]] == [session["id"]]
    missing = await client.post(
        record, json={"status": "COMPLETED", "summary": "요약"}, headers=mentor_h
    )
    assert missing.status_code == 422  # 완료에는 진행 시간
    assert (
        await client.post(
            record,
            json={"status": "COMPLETED", "duration": 30, "summary": "요약"},
            headers=student_h,
        )
    ).status_code == 403  # 담당 멘토만
    done = await client.post(
        record,
        json={"status": "COMPLETED", "duration": 30, "topic": "실제 주제", "summary": "요약"},
        headers=mentor_h,
    )
    assert done.status_code == 200, done.text
    assert (
        done.json()["status"],
        done.json()["record_duration_minutes"],
        done.json()["summary"],
    ) == (
        "COMPLETED",
        30,
        "요약",
    )
    (balance,) = (await client.get("/api/v1/me/balances", headers=student_h)).json()
    assert (balance["remaining_minutes"], balance["used_minutes"]) == (150, 30)  # 짧게 → 차이 환불
    again = await client.post(record, json={"status": "NO_SHOW"}, headers=mentor_h)
    assert again.json()["error"]["code"] == "session_not_recordable"
    edited = await client.patch(record, json={"summary": "고친 요약"}, headers=mentor_h)
    assert edited.json()["summary"] == "고친 요약"
    assert (await client.get(f"{admin_sessions}/unrecorded", headers=admin)).json()["total"] == 0

    # 수강생도 요약·Meet 실제 시각·참여자·차감 상태·신청 요약을 받는다 (A68)
    shown = (
        await client.get(f"/api/v1/mentoring/sessions/{session['id']}", headers=student_h)
    ).json()
    assert shown["summary"] == "고친 요약"
    assert (shown["actual_started_at"], shown["mentor_headline"]) == (None, "백엔드 10년차")
    assert [p["name"] for p in shown["participants"]] == ["가수강"]
    assert shown["balance"] == {"state": "USED", "minutes": 30}  # 짧게 진행 → 차이 환불
    assert (shown["approved_rank"], shown["canceled_by"]) == (1, None)
    assert shown["requested_at"] is not None
    assert "mentor_name" not in shown
    staff = (await client.get(f"{admin_sessions}/{session['id']}", headers=admin)).json()
    assert "actual_started_at" in staff

    note = f"/api/v1/mentoring/sessions/{session['id']}/note"
    assert (await client.get(note, headers=mentor_h)).json()["body"] is None
    saved = await client.put(note, json={"body": "다음엔 테스트 코드"}, headers=mentor_h)
    assert saved.json()["body"] == "다음엔 테스트 코드"
    assert (await client.get(note, headers=student_h)).status_code == 403  # 수강생은 못 본다
    staff_note = await client.get(f"{admin_sessions}/{session['id']}/note", headers=admin)
    assert staff_note.json()["body"] == "다음엔 테스트 코드"
    assert (
        await client.get(f"{admin_sessions}/{session['id']}/note", headers=student_h)
    ).status_code == 403


async def test_artifact_list_and_stream(app: Any, client: AsyncClient, settings: Settings) -> None:
    from collections.abc import AsyncIterator
    from typing import cast

    from fastapi import Request

    from app.contexts.mentoring.application.artifact_service import ArtifactService
    from app.contexts.mentoring.domain.artifact import MentoringArtifact
    from app.contexts.mentoring.domain.enums import MentoringArtifactType
    from app.contexts.mentoring.infrastructure.repositories import (
        TortoiseMentoringArtifactRepository,
        TortoiseMentoringRequestRepository,
        TortoiseMentoringSessionRepository,
        TortoiseTranscriptEntryRepository,
    )
    from app.contexts.mentoring.presentation.artifact_router import get_artifact_service
    from app.contexts.mentoring.presentation.session_router import get_session_queries
    from app.core.clock import SystemClock
    from app.integrations.google.drive import DriveStream

    streamed: list[tuple[str, bool, str | None]] = []

    class FakeArchive:
        async def stream(
            self, file_id: str, *, export_pdf: bool, range_header: str | None
        ) -> DriveStream:
            streamed.append((file_id, export_pdf, range_header))

            async def chunks() -> AsyncIterator[bytes]:
                yield b"part"

            if export_pdf:
                return DriveStream(200, {"content-type": "application/pdf"}, chunks())
            return DriveStream(
                206, {"content-type": "video/mp4", "content-range": "bytes 0-3/10"}, chunks()
            )

        async def export_markdown(self, file_id: str) -> str:
            return f"## {file_id} 요약"

    def service(request: Request) -> ArtifactService:
        state = request.app.state
        return ArtifactService(
            sessions=TortoiseMentoringSessionRepository(),
            requests=TortoiseMentoringRequestRepository(),
            artifacts=TortoiseMentoringArtifactRepository(),
            access=get_session_queries(request),
            source=None,
            archive=cast("Any", FakeArchive()),
            students=state.student_queries,
            cohorts=state.academy_catalog,
            mentors=state.mentor_queries,
            users=state.user_queries,
            clock=SystemClock(),
            entries=TortoiseTranscriptEntryRepository(),
        )

    app.dependency_overrides[get_artifact_service] = service
    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    request_id = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    session_id = (
        await client.post(
            f"{URL}/{request_id}/approve",
            json={"starts_at": ctx["at"].isoformat()},
            headers=mentor_h,
        )
    ).json()["session"]["id"]
    repo = TortoiseMentoringArtifactRepository()
    video = MentoringArtifact(
        session_id=uuid.UUID(session_id),
        drive_file_id="v1",
        artifact_type=MentoringArtifactType.VIDEO,
    )
    video.archived(file_name="녹화.mp4", mime_type="video/mp4", file_size=10)
    doc = MentoringArtifact(
        session_id=uuid.UUID(session_id),
        drive_file_id="t1",
        artifact_type=MentoringArtifactType.TRANSCRIPT,
    )
    doc.archived(
        file_name="전사본", mime_type="application/vnd.google-apps.document", file_size=None
    )
    pending = MentoringArtifact(
        session_id=uuid.UUID(session_id),
        drive_file_id="p1",
        artifact_type=MentoringArtifactType.SUMMARY,
    )
    memo = MentoringArtifact(
        session_id=uuid.UUID(session_id),
        drive_file_id="s1",
        artifact_type=MentoringArtifactType.SUMMARY,
    )
    memo.archived(
        file_name="스마트 메모", mime_type="application/vnd.google-apps.document", file_size=None
    )
    for a in (video, doc, pending, memo):
        await repo.add_if_absent(a)

    base = f"/api/v1/mentoring/sessions/{session_id}/artifacts"
    listed = (await client.get(base, headers=student_h)).json()
    assert {(a["artifact_type"], a["file_name"], a["mime_type"]) for a in listed} == {
        ("VIDEO", "녹화.mp4", "video/mp4"),
        ("TRANSCRIPT", "전사본.pdf", "application/pdf"),
        ("SUMMARY", "스마트 메모.pdf", "application/pdf"),
    }  # 정리 전 파일은 보이지 않는다
    content = await client.get(
        f"{base}/{video.id}/content", headers={**student_h, "Range": "bytes=0-3"}
    )
    assert (content.status_code, content.content) == (206, b"part")
    assert content.headers["content-range"] == "bytes 0-3/10"
    assert "inline; filename*=UTF-8''" in content.headers["content-disposition"]
    pdf = await client.get(f"{base}/{doc.id}/content", headers=mentor_h)
    assert (pdf.status_code, pdf.headers["content-type"]) == (200, "application/pdf")
    assert streamed == [("v1", False, "bytes=0-3"), ("t1", True, None)]
    assert (await client.get(f"{base}/{pending.id}/content", headers=student_h)).status_code == 404

    stranger = bearer(settings, await _approved())
    assert (await client.get(base, headers=stranger)).status_code == 404
    admin_base = (
        f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring/sessions/{session_id}/artifacts"
    )
    assert len((await client.get(admin_base, headers=admin)).json()) == 3
    assert (await client.get(admin_base, headers=student_h)).status_code == 403

    # 서명 링크: 헤더 없이 Range로 재생, 내려받기는 attachment (A68)
    link = await client.post(f"{base}/{video.id}/link", headers=student_h)
    assert link.status_code == 200, link.text
    played = await client.get(link.json()["url"], headers={"Range": "bytes=0-3"})
    assert (played.status_code, played.content) == (206, b"part")
    assert played.headers["content-disposition"].startswith("inline;")
    saved = await client.get(link.json()["download_url"])
    assert saved.headers["content-disposition"].startswith("attachment;")
    assert (await client.post(f"{base}/{video.id}/link", headers=stranger)).status_code == 404
    token = link.json()["url"].split("token=")[1]
    other = await client.get(f"/api/v1/mentoring/artifacts/{doc.id}/stream?token={token}")
    assert (other.status_code, other.json()["error"]["code"]) == (401, "artifact_link_invalid")
    forged = await client.get(f"/api/v1/mentoring/artifacts/{video.id}/stream?token=x.y.z")
    assert forged.status_code == 401
    access_token = student_h["Authorization"].removeprefix("Bearer ")
    reused = await client.get(f"/api/v1/mentoring/artifacts/{video.id}/stream?token={access_token}")
    assert reused.status_code == 401  # access 토큰은 서명 링크로 쓸 수 없다

    # 전사 문장 (A69): TRANSCRIPT만, 회의 기록·녹화 시작은 목록에
    from app.contexts.mentoring.domain.transcript import TranscriptEntry

    await TortoiseTranscriptEntryRepository().add_many(
        [
            TranscriptEntry(
                artifact_id=doc.id,
                sequence=0,
                speaker_name="멘토K",
                meet_name="김멘토",
                text="README부터 봐요",
                started_at=ctx["at"],
            )
        ]
    )
    lines = (await client.get(f"{base}/{doc.id}/entries", headers=student_h)).json()
    assert [(e["speaker_name"], e["text"]) for e in lines] == [("멘토K", "README부터 봐요")]
    assert "meet_name" not in lines[0]  # Meet 원래 이름은 내려주지 않는다
    assert (await client.get(f"{base}/{video.id}/entries", headers=student_h)).status_code == 404
    assert (await client.get(f"{base}/{doc.id}/entries", headers=stranger)).status_code == 404
    assert {"conference_record", "started_at", "ended_at"} <= set(listed[0])

    # 스마트 메모 마크다운 (A68): SUMMARY만
    md = await client.get(f"{base}/{memo.id}/markdown", headers=student_h)
    assert md.json() == {"artifact_id": str(memo.id), "markdown": "## s1 요약"}
    assert (await client.get(f"{base}/{video.id}/markdown", headers=student_h)).status_code == 404
    assert (await client.get(f"{base}/{memo.id}/markdown", headers=stranger)).status_code == 404


async def test_settlement_aggregate_detail_close(
    app: Any, client: AsyncClient, settings: Settings
) -> None:
    from app.core.clock import FixedClock

    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    at = ctx["at"]
    ids = []
    for offset in (0, 3):
        rid = (
            await client.post(
                URL,
                json=_body(ctx, desired_times=[(at + timedelta(hours=offset)).isoformat()]),
                headers=student_h,
            )
        ).json()["id"]
        session = (
            await client.post(
                f"{URL}/{rid}/approve",
                json={"starts_at": (at + timedelta(hours=offset)).isoformat()},
                headers=mentor_h,
            )
        ).json()["session"]
        ids.append(session["id"])
    app.state.clock = FixedClock(at + timedelta(hours=5))
    await client.post(
        f"/api/v1/mentoring/sessions/{ids[0]}/record",
        json={"status": "COMPLETED", "duration": 90, "summary": "요약"},
        headers=mentor_h,
    )  # 두 번째 세션은 미제출

    base = f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring/settlements"
    month = at.strftime("%Y-%m")
    bad = await client.post(f"{base}/aggregate", json={"month": "2026-13"}, headers=admin)
    assert bad.status_code == 422
    assert (
        await client.post(f"{base}/aggregate", json={"month": month}, headers=student_h)
    ).status_code == 403
    agg = (await client.post(f"{base}/aggregate", json={"month": month}, headers=admin)).json()
    (summary,) = agg["settlements"]
    assert (summary["session_count"], summary["total_minutes"], summary["total_amount"]) == (
        1,
        90,
        45000,  # 실제 진행 기준, 시급 30000 × 90분
    )
    assert summary["mentor_name"] == "김멘토"
    listed = (await client.get(base, params={"month": month}, headers=admin)).json()
    assert [s["id"] for s in listed] == [summary["id"]]
    detail = (await client.get(f"{base}/{summary['id']}", headers=admin)).json()
    assert [(i["session_id"], i["amount"]) for i in detail["items"]] == [(ids[0], 45000)]

    preview = (await client.post(f"{base}/{summary['id']}/close", json={}, headers=admin)).json()
    assert (preview["applied"], [u["session_id"] for u in preview["unrecorded"]]) == (
        False,
        [ids[1]],
    )
    closed = (
        await client.post(f"{base}/{summary['id']}/close", json={"confirm": True}, headers=admin)
    ).json()
    assert (closed["applied"], closed["settlement"]["status"]) == (True, "CLOSED")
    again = await client.post(f"{base}/aggregate", json={"month": month}, headers=admin)
    assert again.json()["closed"] == [summary["id"]]


async def test_settlement_csv_and_mentor_view(
    app: Any, client: AsyncClient, settings: Settings
) -> None:
    import csv
    import io

    from app.core.clock import FixedClock

    ctx = await _setup(client, settings)
    student_h, mentor_h, admin = ctx["student_h"], ctx["mentor_h"], ctx["admin"]
    at = ctx["at"]
    rid = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    sid = (
        await client.post(
            f"{URL}/{rid}/approve", json={"starts_at": at.isoformat()}, headers=mentor_h
        )
    ).json()["session"]["id"]
    app.state.clock = FixedClock(at + timedelta(hours=2))
    await client.post(
        f"/api/v1/mentoring/sessions/{sid}/record",
        json={"status": "COMPLETED", "duration": 60, "topic": "포트폴리오", "summary": "요약,쉼표"},
        headers=mentor_h,
    )
    base = f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring/settlements"
    month = at.strftime("%Y-%m")
    (summary,) = (
        await client.post(f"{base}/aggregate", json={"month": month}, headers=admin)
    ).json()["settlements"]

    exported = await client.get(
        f"{base}/export.csv", params={"month": month, "columns": "topic,summary"}, headers=admin
    )
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.content.startswith("﻿".encode())  # BOM
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0][-2:] == ["주제", "요약"]
    assert len(rows) == 2
    record = dict(zip(rows[0], rows[1], strict=True))
    assert (record["멘토"], record["신청자"], record["금액(원)"], record["요약"]) == (
        "김멘토",
        "가수강",
        "30000",
        "요약,쉼표",
    )
    assert record["정산 상태"] == "집계 중"
    assert record["미차감 초과(분)"] == ""  # 신청과 같은 시간이라 없다 (A78)
    bad = await client.get(
        f"{base}/export.csv", params={"month": month, "columns": "x"}, headers=admin
    )
    assert bad.json()["error"]["code"] == "invalid_export_columns"
    single = await client.get(f"{base}/{summary['id']}/export.csv", headers=admin)
    assert len(next(iter(csv.reader(io.StringIO(single.content.decode("utf-8-sig")))))) == 15
    assert (
        await client.get(f"{base}/export.csv", params={"month": month}, headers=student_h)
    ).status_code == 403

    mine = "/api/v1/me/mentor-settlements"
    assert (await client.get(mine, headers=mentor_h)).json() == []  # 마감 전
    await client.post(f"{base}/{summary['id']}/close", json={"confirm": True}, headers=admin)
    listed = (await client.get(mine, headers=mentor_h)).json()
    assert [s["id"] for s in listed] == [summary["id"]]
    assert (listed[0]["bootcamp_name"], listed[0]["cohort_number"]) == (
        summary["bootcamp_name"],
        summary["cohort_number"],
    )
    assert summary["bootcamp_name"]
    assert summary["cohort_number"]
    detail = (await client.get(f"{mine}/{summary['id']}", headers=mentor_h)).json()
    (row,) = detail["items"]
    assert (row["amount"], row["session_topic"], row["requester_name"], row["team_label"]) == (
        30000,
        "포트폴리오",
        "가수강",
        None,
    )
    assert detail["cohort_number"] == summary["cohort_number"]
    assert (await client.get(mine, headers=student_h)).status_code == 404  # 멘토 아님


async def test_chat_notices_follow_request_events(
    app: Any, client: AsyncClient, settings: Settings
) -> None:
    """신청·승인·반려·취소·자동 취소·기록 때 1:1 방에 안내가 남는다 (A57·A58)."""
    from app.core.clock import FixedClock

    ctx = await _setup(client, settings)
    student_h, mentor_h = ctx["student_h"], ctx["mentor_h"]
    later = ctx["at"] + timedelta(hours=2)
    first = (await client.post(URL, json=_body(ctx), headers=student_h)).json()["id"]
    approved = await client.post(
        f"{URL}/{first}/approve", json={"starts_at": ctx["at"].isoformat()}, headers=mentor_h
    )
    session_id = approved.json()["session"]["id"]
    second = (
        await client.post(
            URL, json=_body(ctx, desired_times=[later.isoformat()]), headers=student_h
        )
    ).json()["id"]
    await client.post(f"{URL}/{second}/reject", json={"reason": "일정 불가"}, headers=mentor_h)
    third = (
        await client.post(
            URL, json=_body(ctx, desired_times=[later.isoformat()]), headers=student_h
        )
    ).json()["id"]
    await client.post(f"{URL}/{third}/cancel", json={"reason": "개인 사정"}, headers=student_h)
    await client.post(URL, json=_body(ctx, desired_times=[later.isoformat()]), headers=student_h)
    await client.put(  # 신청 받기를 끄면 대기 신청이 자동 취소된다
        "/api/v1/me/mentor-schedule/accepting", json={"accepting_requests": False}, headers=mentor_h
    )
    app.state.clock = FixedClock(ctx["at"] + timedelta(hours=1))
    recorded = await client.post(
        f"/api/v1/mentoring/sessions/{session_id}/record",
        json={"status": "COMPLETED", "duration": 60, "summary": "요약"},
        headers=mentor_h,
    )
    assert recorded.status_code == 200, recorded.text

    threads = (await client.get("/api/v1/me/mentoring/chat/threads", headers=student_h)).json()
    (thread,) = threads["items"]
    assert thread["unread_count"] == 9
    page = await client.get(
        f"/api/v1/mentoring/chat/threads/{thread['id']}/messages", headers=mentor_h
    )
    items = list(reversed(page.json()["items"]))
    assert {m["sender_kind"] for m in items} == {"SYSTEM"}
    assert [m["body"].split("]")[0] + "]" for m in items] == [
        "[멘토링 신청]",
        "[멘토링 승인]",
        "[멘토링 신청]",
        "[멘토링 반려]",
        "[멘토링 신청]",
        "[멘토링 취소]",
        "[멘토링 신청]",
        "[멘토링 취소]",
        "[멘토링 완료]",
    ]
    assert "주제: 포트폴리오 리뷰" in items[1]["body"]
    assert items[3]["body"].endswith("사유: 일정 불가")
    assert items[5]["body"].endswith("사유: 개인 사정")
    assert "자동 취소" in items[7]["body"]
    assert items[8]["body"].endswith("진행 60분")


async def test_team_session_lists_team_members(client: AsyncClient, settings: Settings) -> None:
    """팀 세션의 참여자는 지금 팀원이다 (A68)."""
    ctx = await _setup(client, settings)
    admin, cohort = ctx["admin"], ctx["cohort"]
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    hours = {"start": "10:00", "end": "19:00"}
    await client.put(
        f"{api}/mentoring-settings",
        json={
            "allow_1_on_1": True,
            "allow_team_mentoring": True,
            "default_1on1_minutes": 180,
            "default_team_minutes": 180,
            "max_pending_requests": 3,
            "weekday_hours": hours,
            "weekend_hours": hours,
        },
        headers=admin,
    )
    mate = make_student(cohort_id=cohort.id, name="나수강")
    await TortoiseStudentRepository().add(mate)
    team = await client.post(
        f"{api}/mentoring-teams",
        json={
            "mentor_id": str(ctx["mentor"].id),
            "student_ids": [str(ctx["student"].id), str(mate.id)],
        },
        headers=admin,
    )
    assert team.status_code == 201, team.text
    granted = await client.post(
        f"{api}/mentoring-balances/grants",
        json={"target": "ALL_TEAMS", "reason": "팀 지급"},
        headers={**admin, "Idempotency-Key": str(new_id())},
    )
    assert granted.status_code == 200, granted.text
    request_id = (
        await client.post(
            URL,
            json=_body(ctx, cohort_id=None, mentor_id=None, team_id=team.json()["id"]),
            headers=ctx["student_h"],
        )
    ).json()["id"]
    teams_url = "/api/v1/me/mentoring-teams"
    stats = (await client.get(teams_url, headers=ctx["student_h"])).json()["as_student"][0]["stats"]
    assert (stats["pending_requests"], stats["pending_requester_name"]) == (1, "가수강")  # A73
    approved = await client.post(
        f"{URL}/{request_id}/approve",
        json={"starts_at": ctx["at"].isoformat()},
        headers=ctx["mentor_h"],
    )
    session = approved.json()["session"]
    assert sorted(p["name"] for p in session["participants"]) == ["가수강", "나수강"]
    stats = (await client.get(teams_url, headers=ctx["student_h"])).json()["as_student"][0]["stats"]
    assert (stats["pending_requests"], stats["upcoming_sessions"]) == (0, 1)
    assert stats["next_session_at"] == session["starts_at"]

    # 세션 목록 팀 필터 (A73): 소속 팀만, 아니면 빈 목록
    mine = "/api/v1/me/mentoring/sessions"
    team_only = await client.get(
        mine, params={"team_id": team.json()["id"]}, headers=ctx["student_h"]
    )
    assert [s["id"] for s in team_only.json()["items"]] == [session["id"]]
    stranger = await client.get(mine, params={"team_id": str(new_id())}, headers=ctx["student_h"])
    assert (stranger.json()["items"], stranger.json()["total"]) == ([], 0)

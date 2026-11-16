"""멘티 목록 API (실제 DB, A59)."""

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved(name: str) -> User:
    user = await create_user(name=name)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def test_lists_mentees_with_team_account_and_filters(
    client: AsyncClient, settings: Settings
) -> None:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    mentor = await create_mentor(await _approved("김멘토"))
    assigned = await client.post(
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
    assert assigned.status_code == 201, assigned.text
    await client.put(
        f"{api}/mentoring-settings", json={"allow_team_mentoring": True}, headers=admin
    )
    student_user = await _approved("가수강")
    repo = TortoiseStudentRepository()
    ga = make_student(cohort_id=cohort.id, name="가수강", user_id=student_user.id)
    na = make_student(cohort_id=cohort.id, name="나수강")
    da = make_student(cohort_id=cohort.id, name="다수강")
    da.end(EnrollmentStatus.DROPPED, on=date(2026, 11, 15))
    removed = make_student(cohort_id=cohort.id, name="라수강", is_removed_in_source=True)
    for s in (ga, na, da, removed):
        await repo.add(s)
    granted = await client.post(
        f"{api}/mentoring-balances/grants",
        json={"target": "ALL_STUDENTS", "minutes": 120, "reason": "기본 지급"},
        headers={**admin, "Idempotency-Key": str(new_id())},
    )
    assert granted.status_code == 200, granted.text
    team = await client.post(
        f"{api}/mentoring-teams",
        json={"mentor_id": str(mentor.id), "student_ids": [str(na.id)]},
        headers=admin,
    )
    assert team.status_code == 201, team.text

    url = f"{api}/mentoring/mentees"
    listed = await client.get(url, headers=admin)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 3  # 원천에서 삭제된 등록은 빠진다
    first, second, third = body["items"]
    assert (first["name"], first["is_signed_up"], first["status"]) == ("가수강", True, "ENROLLED")
    assert first["account"]["remaining_minutes"] == 120
    assert first["team"] is None
    assert (first["pending_request_count"], first["upcoming_session_count"]) == (0, 0)
    assert second["team"]["label"] == "1팀"
    assert (third["name"], third["status"], third["account"]) == ("다수강", "DROPPED", None)

    enrolled = (await client.get(url, params={"status": "ENROLLED"}, headers=admin)).json()
    assert [m["name"] for m in enrolled["items"]] == ["가수강", "나수강"]
    both = await client.get(
        url, params=[("status", "ENROLLED"), ("status", "DROPPED")], headers=admin
    )
    assert both.json()["total"] == 3
    named = (await client.get(url, params={"q": "나"}, headers=admin)).json()
    assert [m["name"] for m in named["items"]] == ["나수강"]
    paged = (await client.get(url, params={"limit": 1, "offset": 2}, headers=admin)).json()
    assert ([m["name"] for m in paged["items"]], paged["total"]) == (["다수강"], 3)

    assert (await client.get(url, headers=bearer(settings, student_user))).status_code == 403
    assert (await client.get(url)).status_code == 401

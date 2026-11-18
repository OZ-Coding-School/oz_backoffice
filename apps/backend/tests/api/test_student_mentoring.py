"""수강생 멘토링 신청 준비 API (실제 DB, A64)."""

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.domain.entities import Cohort
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
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


async def _approved(**overrides: object) -> User:
    user = await create_user(**overrides)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _assign(
    client: AsyncClient, admin: dict[str, str], cohort: Cohort, mentor: Mentor
) -> None:
    response = await client.post(
        f"/api/v1/admin/cohorts/{cohort.id}/mentor-assignments",
        json={
            "mentor_id": str(mentor.id),
            "start_date": "2026-11-01",
            "cost_settlement_policy": "ACTUAL_DURATION",
            "pay_unit": "HOURLY",
            "pay_rate": 30000,
        },
        headers=admin,
    )
    assert response.status_code == 201


async def test_my_enrollments_include_every_status(client: AsyncClient, settings: Settings) -> None:
    user = await _approved()
    students = TortoiseStudentRepository()
    current, past = await create_cohort(cohort_number=12), await create_cohort(cohort_number=3)
    await students.add(make_student(cohort_id=current.id, user_id=user.id))
    await students.add(
        make_student(
            cohort_id=past.id,
            user_id=user.id,
            status=EnrollmentStatus.COMPLETED,
            ended_at=date(2027, 4, 30),
        )
    )
    await students.add(make_student(cohort_id=current.id))  # 다른 사람

    body = (await client.get("/api/v1/me/enrollments", headers=bearer(settings, user))).json()

    # 두 기수의 시작일이 같아(빌더 기본값) 순서 대신 내용만 본다
    assert {(e["cohort_id"], e["status"]) for e in body} == {
        (str(current.id), "ENROLLED"),
        (str(past.id), "COMPLETED"),
    }
    first = next(e for e in body if e["cohort_id"] == str(current.id))
    assert first["cohort_number"] == 12
    assert first["bootcamp_name"].startswith("운영과정")
    assert (first["start_date"], first["end_date"], first["ended_at"]) == (
        "2026-11-01",
        "2027-04-30",
        None,
    )
    mentor = await _approved()
    assert (
        await client.get("/api/v1/me/enrollments", headers=bearer(settings, mentor))
    ).json() == []
    assert (await client.get("/api/v1/me/enrollments")).status_code == 401


async def test_settings_summary_and_mentors(client: AsyncClient, settings: Settings) -> None:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort, other_cohort = await create_cohort(), await create_cohort()
    student_user = await _approved()
    await TortoiseStudentRepository().add(
        make_student(cohort_id=cohort.id, user_id=student_user.id)
    )
    student = bearer(settings, student_user)
    params = {"cohort_id": str(cohort.id)}

    missing = await client.get("/api/v1/me/mentoring/settings", params=params, headers=student)
    assert missing.json()["error"]["code"] == "mentoring_settings_not_configured"
    await client.put(
        f"/api/v1/admin/cohorts/{cohort.id}/mentoring-settings",
        json={"allow_1_on_1": True, "allow_team_mentoring": True, "allowed_duration": 60},
        headers=admin,
    )
    summary = (
        await client.get("/api/v1/me/mentoring/settings", params=params, headers=student)
    ).json()
    assert summary == {
        "cohort_id": str(cohort.id),
        "allow_1_on_1": True,
        "allow_team_mentoring": True,
        "allowed_duration": 60,
        "min_lead_hours": 24,
        "max_pending_requests": 1,
    }

    open_mentor = await create_mentor(
        await _approved(name="김실명"),
        nickname="오즈멘토",
        display_name_preference=DisplayNamePreference.NICKNAME,
        headline="백엔드 10년",
        expertise="Django",
        introduction="소개 글",
        accepting_requests=True,
        profile_image_key="mentors/profile.webp",
    )
    closed_mentor = await create_mentor(await _approved(name="나멘토"), headline="쉬는 중")
    elsewhere = await create_mentor(await _approved(), accepting_requests=True)
    for mentor in (open_mentor, closed_mentor):
        await _assign(client, admin, cohort, mentor)
    await _assign(client, admin, other_cohort, elsewhere)

    cards = (
        await client.get("/api/v1/me/mentoring/mentors", params=params, headers=student)
    ).json()
    assert [c["mentor_id"] for c in cards] == [str(open_mentor.id)]  # 신청 받는 멘토만
    card = cards[0]
    assert (card["display_name"], card["headline"], card["expertise"]) == (
        "오즈멘토",
        "백엔드 10년",
        "Django",
    )
    assert card["profile_image_url"].startswith("http")
    assert "introduction" not in card
    assert "김실명" not in str(cards)

    # 단건은 신청을 받지 않아도 배정된 멘토면 보인다 (팀 멘토 확인·소개 모달)
    closed = await client.get(
        f"/api/v1/me/mentoring/mentors/{closed_mentor.id}", params=params, headers=student
    )
    assert closed.status_code == 200
    assert (closed.json()["display_name"], closed.json()["accepting_requests"]) == ("나멘토", False)
    assert closed.json()["profile_image_url"] is None
    profile = await client.get(
        f"/api/v1/me/mentoring/mentors/{open_mentor.id}", params=params, headers=student
    )
    assert profile.json()["introduction"] == "소개 글"
    for mentor_id in (elsewhere.id, new_id()):
        response = await client.get(
            f"/api/v1/me/mentoring/mentors/{mentor_id}", params=params, headers=student
        )
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "mentor_not_assigned",
        )

    # 그 기수의 수강 중 수강생만
    stranger = bearer(settings, await _approved())
    for url in (
        "/api/v1/me/mentoring/settings",
        "/api/v1/me/mentoring/mentors",
        f"/api/v1/me/mentoring/mentors/{open_mentor.id}",
    ):
        denied = await client.get(url, params=params, headers=stranger)
        assert (denied.status_code, denied.json()["error"]["code"]) == (
            403,
            "not_enrolled_in_cohort",
        )
        assert (await client.get(url, params=params)).status_code == 401

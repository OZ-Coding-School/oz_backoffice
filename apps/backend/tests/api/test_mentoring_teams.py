"""멘토링 팀 API (실제 DB, A39)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user
from tests.factories.staff_review import create_applicant, seed_roles

pytestmark = pytest.mark.api

PROJECT = "PROJECT_MENTORING"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved(**overrides: Any) -> User:
    user = await create_user(**overrides)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _setup(client: AsyncClient, settings: Settings) -> dict[str, Any]:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    mentor_user = await _approved(name="김멘토")
    mentor = await create_mentor(
        mentor_user, nickname="멘토K", display_name_preference=DisplayNamePreference.NICKNAME
    )
    await client.post(
        f"{api}/mentor-assignments",
        json={
            "mentor_id": str(mentor.id),
            "period_type": PROJECT,
            "start_date": "2026-11-01",
            "cost_settlement_policy": "ACTUAL_DURATION",
            "pay_unit": "HOURLY",
            "pay_rate": 30000,
        },
        headers=admin,
    )
    await client.put(
        f"{api}/mentoring-settings",
        json={"allow_team_mentoring": True},
        headers=admin,
    )
    student_user = await _approved()
    repo = TortoiseStudentRepository()
    signed = make_student(cohort_id=cohort.id, name="가수강", user_id=student_user.id)
    pending = make_student(cohort_id=cohort.id, name="나수강")
    dropped = make_student(cohort_id=cohort.id, name="다수강", status=EnrollmentStatus.DROPPED)
    for s in (signed, pending, dropped):
        await repo.add(s)
    return {
        "admin": admin,
        "cohort": cohort,
        "path": f"{api}/mentoring-teams",
        "mentor": mentor,
        "mentor_h": bearer(settings, mentor_user),
        "student_h": bearer(settings, student_user),
        "signed": signed,
        "pending": pending,
        "dropped": dropped,
    }


async def test_team_lifecycle(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    path, admin = ctx["path"], ctx["admin"]

    unassigned = await client.get(
        f"{path}/unassigned-students", params={"period_type": PROJECT}, headers=admin
    )
    assert [(s["name"], s["is_signed_up"]) for s in unassigned.json()] == [
        ("가수강", True),
        ("나수강", False),
    ]
    created = await client.post(
        path,
        json={
            "period_type": PROJECT,
            "mentor_id": str(ctx["mentor"].id),
            "student_ids": [str(ctx["signed"].id)],
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    team = created.json()
    assert (team["team_number"], team["label"]) == (1, "1팀")
    assert (team["mentor"]["name"], team["mentor"]["display_name"]) == ("김멘토", "멘토K")
    team_url = f"{path}/{team['id']}"

    dropped = await client.post(
        f"{team_url}/members", json={"student_id": str(ctx["dropped"].id)}, headers=admin
    )
    assert dropped.json()["error"]["code"] == "student_not_enrolled"
    added = await client.post(
        f"{team_url}/members", json={"student_id": str(ctx["pending"].id)}, headers=admin
    )
    assert [m["name"] for m in added.json()["members"]] == ["가수강", "나수강"]
    second = await client.post(
        path,
        json={
            "period_type": PROJECT,
            "mentor_id": str(ctx["mentor"].id),
            "student_ids": [str(ctx["pending"].id)],
        },
        headers=admin,
    )
    assert second.json()["error"]["code"] == "student_in_other_team"

    renamed = await client.patch(team_url, json={"name": "알파"}, headers=admin)
    assert renamed.json()["label"] == "알파"
    removed = await client.delete(f"{team_url}/members/{ctx['pending'].id}", headers=admin)
    assert [m["name"] for m in removed.json()["members"]] == ["가수강"]
    listed = await client.get(path, params={"period_type": PROJECT}, headers=admin)
    assert [t["id"] for t in listed.json()] == [team["id"]]

    mine = (await client.get("/api/v1/me/mentoring-teams", headers=ctx["student_h"])).json()
    (my_team,) = mine["as_student"]
    assert my_team["mentor"] == {"mentor_id": str(ctx["mentor"].id), "display_name": "멘토K"}
    assert "name" not in my_team["mentor"]
    assert mine["as_mentor"] == []
    as_mentor = (await client.get("/api/v1/me/mentoring-teams", headers=ctx["mentor_h"])).json()
    assert [t["label"] for t in as_mentor["as_mentor"]] == ["알파"]

    assert (await client.delete(team_url, headers=admin)).status_code == 204
    assert (await client.get(path, headers=admin)).json() == []


async def test_team_rules_and_permissions(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    path, admin = ctx["path"], ctx["admin"]
    other_mentor = await create_mentor()
    unassigned = await client.post(
        path, json={"period_type": PROJECT, "mentor_id": str(other_mentor.id)}, headers=admin
    )
    assert unassigned.json()["error"]["code"] == "mentor_not_assigned"
    regular = await client.post(
        path,
        json={"period_type": "REGULAR_MENTORING", "mentor_id": str(ctx["mentor"].id)},
        headers=admin,
    )
    assert regular.json()["error"]["code"] == "mentor_not_assigned"

    await client.put(
        f"/api/v1/admin/cohorts/{ctx['cohort'].id}/mentoring-settings",
        json={"allow_1_on_1": True},
        headers=admin,
    )
    not_allowed = await client.post(
        path, json={"period_type": PROJECT, "mentor_id": str(ctx["mentor"].id)}, headers=admin
    )
    assert not_allowed.json()["error"]["code"] == "team_mentoring_not_allowed"

    await seed_roles()
    assistant_user = await create_applicant()
    assistant_user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(assistant_user)
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        assistant_user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, ctx["cohort"].id
    )
    assistant = bearer(settings, assistant_user)
    assert (await client.get(path, headers=assistant)).status_code == 200  # 조교도 팀 구성
    other_path = f"/api/v1/admin/cohorts/{(await create_cohort()).id}/mentoring-teams"
    assert (await client.get(other_path, headers=assistant)).status_code == 403
    assert (await client.get(path, headers=ctx["student_h"])).status_code == 403
    assert (await client.get(path)).status_code == 401

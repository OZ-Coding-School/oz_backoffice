"""기수 멘토 배정·멘토 활성화 API (실제 DB)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.domain.entities import Cohort
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import ASSISTANT, MANAGER, give_role
from tests.factories.educator import create_mentor, create_mentor_contract, create_user
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

API = "/api/v1/admin"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _approved(user: User) -> User:
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _staff(settings: Settings, role: str, cohort_id: object) -> dict[str, str]:
    user = await _approved(await create_applicant())
    await give_role(user.id, role, cohort_id=cohort_id)  # type: ignore[arg-type]
    return bearer(settings, user)


async def _mentor(**overrides: Any) -> Mentor:
    user = await _approved(await create_user(name="김멘토"))
    return await create_mentor(user, **overrides)


async def _body(mentor: Mentor, cohort: Cohort, **overrides: Any) -> dict[str, Any]:
    """근거 계약(A110)을 그 기수에 새로 만들어 붙인다. 계약 칸은 `contract`로 바꾼다."""
    contract = await create_mentor_contract(
        mentor.id,
        bootcamp_id=cohort.bootcamp_id,
        cohort_id=cohort.id,
        **overrides.pop("contract", {}),
    )
    body: dict[str, Any] = {
        "mentor_id": str(mentor.id),
        "contract_id": str(contract.id),
        "start_date": "2026-11-01",
    }
    body.update(overrides)
    return body


async def test_assignment_crud(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    mentor = await _mentor(nickname="멘토K", display_name_preference=DisplayNamePreference.NICKNAME)
    path = f"{API}/cohorts/{cohort.id}/mentor-assignments"

    body = await _body(mentor, cohort)
    created = await client.post(path, json=body, headers=admin)
    assert created.status_code == 201, created.text
    data = created.json()
    assert (data["mentor_name"], data["mentor_display_name"]) == ("김멘토", "멘토K")
    assert data["end_date"] is None
    assert (data["contract_id"], data["contract"]["unit_price"]) == (body["contract_id"], 30000)
    assert data["contract"]["mentoring_time_basis"] == "ACTUAL_DURATION"
    item = f"{path}/{data['id']}"

    duplicate = await client.post(path, json=await _body(mentor, cohort), headers=admin)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "assignment_already_exists"
    outside = await client.post(
        path,
        json=await _body(mentor, cohort, start_date="2026-10-31"),
        headers=admin,
    )
    assert outside.json()["error"]["code"] == "assignment_start_outside_cohort"
    short = await client.post(
        path,
        json=await _body(mentor, cohort, contract={"end_date": date(2026, 10, 31)}),
        headers=admin,
    )
    assert short.json()["error"]["code"] == "assignment_outside_contract_period"

    updated = await client.patch(item, json={"end_date": "2027-08-31"}, headers=admin)
    assert updated.json()["end_date"] == "2027-08-31"
    cleared = await client.patch(item, json={"end_date": None}, headers=admin)
    assert cleared.json()["end_date"] is None

    deleted = await client.delete(item, headers=admin)
    assert deleted.status_code == 200
    assert (deleted.json()["is_active"], deleted.json()["deactivation_reason"]) == (False, "MANUAL")
    assert (await client.get(path, headers=admin)).json() == []
    listed = await client.get(path, params={"include_inactive": "true"}, headers=admin)
    assert [a["id"] for a in listed.json()] == [data["id"]]

    reactivated = await client.post(f"{item}/reactivate", headers=admin)
    assert reactivated.json()["is_active"] is True


async def test_assignment_permissions(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    cohort, other = await create_cohort(), await create_cohort()
    mentor = await _mentor()
    path = f"{API}/cohorts/{cohort.id}/mentor-assignments"
    manager = await _staff(settings, MANAGER, cohort.id)
    assistant = await _staff(settings, ASSISTANT, cohort.id)

    assert (await client.get(path)).status_code == 401
    assert (
        await client.post(path, json=await _body(mentor, cohort), headers=manager)
    ).status_code == 201
    assert (await client.get(path, headers=assistant)).status_code == 403
    other_path = f"{API}/cohorts/{other.id}/mentor-assignments"
    assert (await client.get(other_path, headers=manager)).status_code == 403
    # 멘토 활성화(mentor.manage)는 매니저 가능, 조교 불가
    deactivate = f"{API}/mentors/{mentor.id}/deactivate"
    assert (await client.post(deactivate, json={}, headers=assistant)).status_code == 403
    assert (await client.post(deactivate, json={}, headers=manager)).status_code == 200


async def test_mentor_deactivation_flow(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    cohort = await create_cohort()
    mentor = await _mentor()
    path = f"{API}/cohorts/{cohort.id}/mentor-assignments"
    regular = (await client.post(path, json=await _body(mentor, cohort), headers=admin)).json()
    second = await create_cohort()
    other_path = f"{API}/cohorts/{second.id}/mentor-assignments"
    project = (
        await client.post(other_path, json=await _body(mentor, second), headers=admin)
    ).json()

    preview = await client.post(f"{API}/mentors/{mentor.id}/deactivate", json={}, headers=admin)
    assert preview.status_code == 200
    assert preview.json()["applied"] is False
    assert preview.json()["is_active"] is True
    assert "2건" in preview.json()["notice"]
    assert {a["id"] for a in preview.json()["assignments"]} == {regular["id"], project["id"]}

    done = await client.post(
        f"{API}/mentors/{mentor.id}/deactivate", json={"confirm": True}, headers=admin
    )
    assert (done.json()["applied"], done.json()["is_active"]) == (True, False)
    assert (await client.get(path, headers=admin)).json() == []
    blocked = await client.post(f"{path}/{regular['id']}/reactivate", headers=admin)
    assert blocked.json()["error"]["code"] == "mentor_inactive"
    third = await create_cohort()
    new = await client.post(
        f"{API}/cohorts/{third.id}/mentor-assignments",
        json=await _body(mentor, third),
        headers=admin,
    )
    assert new.json()["error"]["code"] == "mentor_inactive"
    profile = await client.get(f"{API}/mentors/{mentor.id}/profile", headers=admin)
    assert profile.json()["is_active"] is False

    activated = await client.post(f"{API}/mentors/{mentor.id}/activate", headers=admin)
    assert activated.json()["is_active"] is True
    assert {a["id"] for a in activated.json()["restorable"]} == {regular["id"], project["id"]}

    bulk = await client.post(
        f"{API}/mentors/{mentor.id}/mentor-assignments/reactivate",
        json={"assignment_ids": [regular["id"], regular["id"]]},
        headers=admin,
    )
    assert [a["id"] for a in bulk.json()["reactivated"]] == [regular["id"]]
    assert bulk.json()["failed"] == []
    again = await client.post(
        f"{API}/mentors/{mentor.id}/mentor-assignments/reactivate",
        json={"assignment_ids": [regular["id"], project["id"]]},
        headers=admin,
    )
    assert [a["id"] for a in again.json()["reactivated"]] == [project["id"]]
    assert [f["code"] for f in again.json()["failed"]] == ["assignment_already_active"]


async def test_mentor_sees_own_assignments(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    cohort = await create_cohort(cohort_number=3)
    mentor = await _mentor()
    path = f"{API}/cohorts/{cohort.id}/mentor-assignments"
    created = (
        await client.post(
            path,
            json=await _body(mentor, cohort, contract={"no_show_pay_amount": 10000}),
            headers=admin,
        )
    ).json()
    user = await TortoiseUserRepository().get(mentor.account_id)
    assert user is not None
    me = bearer(settings, user)

    mine = await client.get("/api/v1/me/mentor-assignments", headers=me)
    assert mine.status_code == 200
    (item,) = mine.json()
    contract = item["contract"]
    assert (item["id"], item["cohort_number"], contract["unit_price"]) == (created["id"], 3, 30000)
    assert contract["no_show_pay_amount"] == 10000
    assert item["bootcamp_name"].startswith("운영과정")
    await client.delete(f"{path}/{created['id']}", headers=admin)
    assert (await client.get("/api/v1/me/mentor-assignments", headers=me)).json() == []
    past = await client.get(
        "/api/v1/me/mentor-assignments", params={"include_inactive": "true"}, headers=me
    )
    assert len(past.json()) == 1

    stranger = await _approved(await create_user())
    missing = await client.get("/api/v1/me/mentor-assignments", headers=bearer(settings, stranger))
    assert missing.json()["error"]["code"] == "mentor_profile_not_found"


async def test_admin_lists_assignments_of_mentor(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    """멘토 단위 배정 조회 (A101): 비활성 포함, 활성 먼저."""
    old, now = await create_cohort(cohort_number=11), await create_cohort(cohort_number=12)
    mentor = await _mentor()
    ended = (
        await client.post(
            f"{API}/cohorts/{old.id}/mentor-assignments",
            json=await _body(mentor, old),
            headers=admin,
        )
    ).json()
    await client.delete(f"{API}/cohorts/{old.id}/mentor-assignments/{ended['id']}", headers=admin)
    active = (
        await client.post(
            f"{API}/cohorts/{now.id}/mentor-assignments",
            json=await _body(mentor, now),
            headers=admin,
        )
    ).json()

    listed = await client.get(f"{API}/mentors/{mentor.id}/mentor-assignments", headers=admin)
    assert listed.status_code == 200
    assert [(a["id"], a["cohort_number"], a["is_active"]) for a in listed.json()] == [
        (active["id"], 12, True),
        (ended["id"], 11, False),
    ]
    assert listed.json()[1]["deactivation_reason"] == "MANUAL"

    missing = await client.get(
        f"{API}/mentors/{active['cohort_id']}/mentor-assignments", headers=admin
    )
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "mentor_not_found")


async def test_contract_candidates_and_contract_end(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    """근거 계약 후보 (A110), 계약을 해지하면 그 계약을 근거로 한 배정이 꺼진다."""
    cohort = await create_cohort()
    mentor = await _mentor()
    path = f"{API}/cohorts/{cohort.id}/mentor-assignments"
    common = await create_mentor_contract(mentor.id, bootcamp_id=cohort.bootcamp_id)
    await create_mentor_contract(  # 다른 과정 계약은 후보가 아니다
        mentor.id, bootcamp_id=(await create_cohort()).bootcamp_id
    )
    listed = await client.get(
        f"{path}/contract-candidates", params={"mentor_id": str(mentor.id)}, headers=admin
    )
    assert listed.status_code == 200, listed.text
    assert [c["id"] for c in listed.json()] == [str(common.id)]

    created = await client.post(
        path,
        json={
            "mentor_id": str(mentor.id),
            "contract_id": str(common.id),
            "start_date": "2026-11-01",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    # 변경 계약으로 기간이 줄면 배정 기간도 줄인다
    amended = await client.post(
        f"{API}/contracts/{common.id}/amendments",
        json={
            "amended_on": "2026-11-20",
            "reason": "기간 단축",
            "changes": {"end_date": "2027-01-31"},
        },
        headers=admin,
    )
    assert amended.status_code in (200, 201), amended.text
    trimmed = (await client.get(path, headers=admin)).json()
    assert [(a["end_date"], a["contract"]["end_date"]) for a in trimmed] == [
        ("2027-01-31", "2027-01-31")
    ]
    moved = await client.post(
        f"{API}/contracts/{common.id}/link",
        json={"mentor_id": str((await _mentor()).id)},
        headers=admin,
    )
    assert moved.json()["error"]["code"] == "mentor_contract_move_forbidden"
    ended = await client.post(
        f"{API}/contracts/{common.id}/terminate",
        json={"reason": "TERMINATED_BY_MUTUAL_AGREEMENT"},
        headers=admin,
    )
    assert ended.status_code == 200, ended.text
    after = (await client.get(path, params={"include_inactive": "true"}, headers=admin)).json()
    assert [(a["is_active"], a["deactivation_reason"]) for a in after] == [
        (False, "CONTRACT_ENDED")
    ]

"""전체 회원 API (decisions A94): 승인 계정 목록·종류별 연결 정보·비활성화·활성화 (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.access import give_permissions
from tests.factories.educator import create_mentor, create_user
from tests.factories.organization import create_employee

pytestmark = pytest.mark.api
URL = "/api/v1/admin/users"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def approved(**overrides: object) -> User:
    user = await create_user(**overrides)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


@pytest.fixture
async def boss(settings: Settings) -> User:
    return (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user


async def test_list_detail_and_links(client: AsyncClient, settings: Settings, boss: User) -> None:
    admin = bearer(settings, boss)
    student = await approved(name="김수강")
    await create_user(name="대기중")  # 승인 전은 보이지 않는다
    cohort = await create_cohort(cohort_number=12)
    await TortoiseStudentRepository().add(make_student(cohort_id=cohort.id, user_id=student.id))
    mentor_user = await approved(name="이멘토", account_type=AccountType.MENTOR)
    await create_mentor(mentor_user)
    employee = await create_employee()
    staff_user = await TortoiseUserRepository().get(employee.user_id)
    assert staff_user is not None
    staff_user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(staff_user)

    page = (await client.get(URL, headers=admin)).json()
    names = [m["name"] for m in page["items"]]
    assert "대기중" not in names
    assert {"김수강", "이멘토"} <= set(names)
    assert page["counts"]["MENTOR"] == 1
    assert page["counts"]["STUDENT"] >= 1
    only = (await client.get(URL, params={"account_type": "MENTOR"}, headers=admin)).json()
    assert [m["name"] for m in only["items"]] == ["이멘토"]
    found = (await client.get(URL, params={"q": "김수"}, headers=admin)).json()
    assert [m["name"] for m in found["items"]] == ["김수강"]

    detail = (await client.get(f"{URL}/{student.id}", headers=admin)).json()
    assert [(e["cohort_number"], e["status"]) for e in detail["enrollments"]] == [(12, "ENROLLED")]
    mentor = (await client.get(f"{URL}/{mentor_user.id}", headers=admin)).json()
    assert (mentor["assignments"], mentor["contract_count"]) == ([], 0)
    staff = (await client.get(f"{URL}/{employee.user_id}", headers=admin)).json()
    assert staff["department_name"]
    assert staff["position_name"]


async def test_deactivate_and_activate(client: AsyncClient, settings: Settings, boss: User) -> None:
    admin = bearer(settings, boss)
    member = await approved(name="박회원")
    mine = bearer(settings, member)
    assert (await client.get("/api/v1/me", headers=mine)).status_code == 200

    missing = await client.post(f"{URL}/{member.id}/deactivate", json={}, headers=admin)
    assert missing.status_code == 422
    off = await client.post(
        f"{URL}/{member.id}/deactivate", json={"reason": "부정 사용"}, headers=admin
    )
    assert (off.status_code, off.json()["is_active"]) == (200, False)
    assert off.json()["history"][0] == {
        "action": "DEACTIVATE",
        "reason": "부정 사용",
        "actor_name": boss.name,
        "at": off.json()["history"][0]["at"],
    }
    # 로그인 중인 access 토큰도 막힌다
    blocked = await client.get("/api/v1/me", headers=mine)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (401, "account_disabled")
    inactive = (await client.get(URL, params={"status": "inactive"}, headers=admin)).json()
    assert [m["name"] for m in inactive["items"]] == ["박회원"]

    on = await client.post(f"{URL}/{member.id}/activate", json={}, headers=admin)
    assert (on.status_code, on.json()["is_active"]) == (200, True)
    assert [h["action"] for h in on.json()["history"]] == ["ACTIVATE", "DEACTIVATE"]
    assert (await client.get("/api/v1/me", headers=mine)).status_code == 200


async def test_rules_and_permissions(client: AsyncClient, settings: Settings, boss: User) -> None:
    admin = bearer(settings, boss)
    me = await client.post(f"{URL}/{boss.id}/deactivate", json={"reason": "x"}, headers=admin)
    assert (me.status_code, me.json()["error"]["code"]) == (409, "cannot_deactivate_self")

    viewer = await approved(name="조회만", email="viewer@nextrunners.co.kr")
    await give_permissions(viewer.id, {"member.user.read"})
    headers = bearer(settings, viewer)
    assert (await client.get(URL, headers=headers)).status_code == 200
    denied = await client.post(f"{URL}/{boss.id}/deactivate", json={"reason": "x"}, headers=headers)
    assert denied.status_code == 403

    manager = await approved(name="관리", email="manager2@nextrunners.co.kr")
    await give_permissions(manager.id, {"member.user.read", "member.user.manage"})
    last = await client.post(
        f"{URL}/{boss.id}/deactivate", json={"reason": "x"}, headers=bearer(settings, manager)
    )
    assert (last.status_code, last.json()["error"]["code"]) == (409, "last_super_admin")
    gone = await client.get(f"{URL}/{viewer.id}x", headers=admin)
    assert gone.status_code == 422

"""계약 응답의 사람 이름·멘토 필터·담당 직원 후보 (decisions A103)."""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.educator import (
    create_instructor,
    create_mentor,
    create_user,
    mentor_contract_json,
)
from tests.factories.organization import create_employee

API = "/api/v1/admin"


async def _admin(settings: Settings) -> tuple[dict[str, str], str]:
    """최고 관리자이면서 직원인 사람 (후보의 '나')"""
    result = await create_super_admin("boss@nextrunners.co.kr", name="김관리", settings=settings)
    employee = await create_employee(result.user)
    token, _ = JWTService(settings).encode(str(result.user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}, str(employee.id)


async def _body(manager_id: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        **(await mentor_contract_json()),
        "contractor_name": "김멘토",
        "contractor_phone": "010-1234-5678",
        "title": "2026 멘토 계약",
        "start_date": "2026-01-01",
        "end_date": "2099-12-31",
        "manager_employee_id": manager_id,
    }
    body.update(overrides)
    return body


async def test_names_and_mentor_filter(
    client: AsyncClient, settings: Settings, s3_bucket: str
) -> None:
    admin, me = await _admin(settings)
    mentor = await create_mentor(
        await create_user(name="김멘토"),
        nickname="멘토K",
        display_name_preference=DisplayNamePreference.NICKNAME,
    )
    instructor = await create_instructor(await create_user(name="박강사"))

    created = await client.post(
        f"{API}/contracts", json=await _body(me, mentor_id=str(mentor.id)), headers=admin
    )
    assert created.status_code == 201, created.text
    assert created.json()["manager_name"] == "김관리"

    assert created.json()["linked_profile"] == {"name": "김멘토", "display_name": "멘토K"}

    other = await client.post(
        f"{API}/contracts",
        json=await _body(
            me,
            contract_type="INSTRUCTOR",
            no_show_pay_amount=None,
            mentoring_time_basis=None,
            contractor_name="박강사",
        ),
        headers=admin,
    )
    await client.post(
        f"{API}/contracts/{other.json()['id']}/link",
        json={"instructor_id": str(instructor.id)},
        headers=admin,
    )
    listed = (await client.get(f"{API}/contracts", headers=admin)).json()["items"]
    assert [(c["contractor_name"], c["linked_profile"]) for c in listed] == [
        ("박강사", {"name": "박강사", "display_name": "박강사"}),
        ("김멘토", {"name": "김멘토", "display_name": "멘토K"}),
    ]

    # 멘토 필터: 그 멘토에 연결된 계약만
    only = await client.get(f"{API}/contracts", params={"mentor_id": str(mentor.id)}, headers=admin)
    assert [c["id"] for c in only.json()["items"]] == [created.json()["id"]]


async def test_manager_candidates(client: AsyncClient, settings: Settings, s3_bucket: str) -> None:
    admin, me = await _admin(settings)
    for name in ("이김관", "김관리자", "박직원"):
        await create_employee(await create_user(name=name))

    url = f"{API}/contracts/manager-candidates"
    everyone = (await client.get(url, headers=admin)).json()
    assert [(c["name"], c["is_me"]) for c in everyone][:1] == [("김관리", True)]
    assert len(everyone) == 4
    assert {"employee_id", "email", "department_name", "team_name", "position_name"} <= set(
        everyone[0]
    )
    assert everyone[0]["employee_id"] == me

    found = (await client.get(url, params={"q": "김관"}, headers=admin)).json()
    assert [c["name"] for c in found] == ["김관리", "김관리자", "이김관"]

    assert (await client.get(url)).status_code == 401
    member = await create_user()
    token, _ = JWTService(settings).encode(str(member.id), "access", now=datetime.now(UTC))
    forbidden = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403

"""가입 전 멘토 (decisions A104): 계약을 만들면 생기고, 목록·단건에 '가입 전'으로 보인다."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.educator.infrastructure.models import MentorModel
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.educator import create_mentor, create_user
from tests.factories.organization import create_employee

API = "/api/v1/admin"


@pytest.fixture
async def admin(settings: Settings, s3_bucket: str) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    token, _ = JWTService(settings).encode(str(result.user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


def _body(manager_id: str, name: str = "새멘토", phone: str = "010-5555-6666") -> dict[str, str]:
    return {
        "educator_type": "MENTOR",
        "contractor_name": name,
        "contractor_phone": phone,
        "title": "2026 멘토 계약",
        "start_date": "2026-01-01",
        "end_date": "2099-12-31",
        "manager_employee_id": manager_id,
    }


async def test_pending_mentor_lifecycle(client: AsyncClient, admin: dict[str, str]) -> None:
    manager = str((await create_employee()).id)
    created = await client.post(f"{API}/contracts", json=_body(manager), headers=admin)
    assert created.status_code == 201, created.text
    mentor_id = created.json()["mentor_id"]
    assert created.json()["linked_profile"] == {"name": "새멘토", "display_name": "새멘토"}

    one = (await client.get(f"{API}/mentors/{mentor_id}", headers=admin)).json()
    assert {k: one[k] for k in ("user_id", "name", "email", "phone_number", "is_active")} == {
        "user_id": None,
        "name": "새멘토",
        "email": None,
        "phone_number": "01055556666",
        "is_active": False,
    }
    assert (one["is_registered"], one["contract_count"]) == (False, 1)

    # 가입한 멘토와 함께 상태로 거른다
    await create_mentor(await create_user(name="가입멘토"))
    pending = await client.get(f"{API}/mentors", params={"status": "pending"}, headers=admin)
    assert [m["name"] for m in pending.json()["items"]] == ["새멘토"]
    active = await client.get(f"{API}/mentors", params={"status": "active"}, headers=admin)
    assert [m["name"] for m in active.json()["items"]] == ["가입멘토"]
    found = await client.get(f"{API}/mentors", params={"q": "5555"}, headers=admin)
    assert [m["name"] for m in found.json()["items"]] == ["새멘토"]

    # 같은 사람이면 같은 가입 전 멘토에 붙는다
    again = await client.post(f"{API}/contracts", json=_body(manager), headers=admin)
    assert again.json()["mentor_id"] == mentor_id

    # 가입 전 멘토는 활성화·신청 받기를 할 수 없다
    activate = await client.post(f"{API}/mentors/{mentor_id}/activate", headers=admin)
    assert activate.json()["error"]["code"] == "mentor_not_registered"
    accepting = await client.put(
        f"{API}/mentors/{mentor_id}/schedule/accepting",
        json={"accepting_requests": True},
        headers=admin,
    )
    assert accepting.status_code == 422

    # 계약을 모두 지우면 가입 전 멘토도 사라진다
    for contract_id in (created.json()["id"], again.json()["id"]):
        deleted = await client.delete(f"{API}/contracts/{contract_id}", headers=admin)
        assert deleted.status_code == 204
    assert not await MentorModel.exists(id=mentor_id)


async def test_pending_mentor_needs_contact(client: AsyncClient, admin: dict[str, str]) -> None:
    """DB가 계정도 연락처도 없는 멘토를 막는다."""
    from tortoise.exceptions import IntegrityError

    with pytest.raises(IntegrityError):
        await MentorModel.create(user_id=None, is_active=False)
    with pytest.raises(IntegrityError):
        await MentorModel.create(
            user_id=None, contact_name="가", contact_phone="01011112222", is_active=True
        )

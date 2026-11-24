"""계약·계약서 관리 API (실제 DB + S3 에뮬레이터 floci)."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import ASSISTANT, MANAGER, give_role
from tests.factories.educator import create_instructor, create_mentor
from tests.factories.organization import create_employee
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

API = "/api/v1/admin"
PDF = b"%PDF-1.7\n" + b"0" * 200


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings, s3_bucket: str) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _staff(settings: Settings, role: str) -> dict[str, str]:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await give_role(user.id, role, cohort_id=(await create_cohort()).id)
    return bearer(settings, user)


async def _upload(client: AsyncClient, h: dict[str, str], body: bytes = PDF) -> httpx.Response:
    """업로드 요청 → floci로 직접 업로드 → 확정."""
    ticket = await client.post(
        f"{API}/contract-files/uploads", json={"file_name": "멘토 계약서.pdf"}, headers=h
    )
    assert ticket.status_code == 201, ticket.text
    data = ticket.json()
    async with httpx.AsyncClient(timeout=10) as s3:
        uploaded = await s3.post(
            data["url"],
            data=data["fields"],
            files={"file": ("contract.pdf", body, "application/pdf")},
        )
    assert uploaded.status_code in (200, 201, 204), uploaded.text
    return await client.post(f"{API}/contract-files/uploads/{data['upload_id']}/confirm", headers=h)


async def _contract_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "educator_type": "MENTOR",
        "contractor_name": "김멘토",
        "contractor_phone": "010-1234-5678",
        "contractor_email": "Mentor@Example.com",
        "title": "2026 멘토 계약",
        "start_date": "2026-01-01",
        "end_date": "2099-12-31",
        "manager_employee_id": str((await create_employee()).id),
    }
    body.update(overrides)
    return body


async def test_contract_lifecycle(client: AsyncClient, admin: dict[str, str]) -> None:
    created = await client.post(f"{API}/contracts", json=await _contract_body(), headers=admin)
    assert created.status_code == 201, created.text
    contract = created.json()
    assert (contract["status"], contract["contract_file"]) == ("DRAFT", None)
    assert (contract["contractor_phone"], contract["contractor_email"]) == (
        "01012345678",
        "mentor@example.com",
    )
    path = f"{API}/contracts/{contract['id']}"

    no_file = await client.post(f"{path}/confirm", headers=admin)
    assert no_file.status_code == 422
    assert no_file.json()["error"]["code"] == "contract_file_required"

    file = await _upload(client, admin)
    assert file.status_code == 201, file.text
    assert (file.json()["file_name"], file.json()["file_size"]) == ("멘토 계약서.pdf", len(PDF))
    attached = await client.patch(path, json={"contract_file_id": file.json()["id"]}, headers=admin)
    assert attached.json()["contract_file"]["id"] == file.json()["id"]

    confirmed = await client.post(f"{path}/confirm", headers=admin)
    assert confirmed.json()["status"] == "ACTIVE"
    locked = await client.patch(path, json={"title": "변경"}, headers=admin)
    assert locked.status_code == 422
    assert locked.json()["error"]["code"] == "contract_not_editable"
    assert (await client.delete(path, headers=admin)).status_code == 422

    url = await client.get(f"{path}/file-url", headers=admin)
    assert url.status_code == 200
    async with httpx.AsyncClient(timeout=10) as s3:
        downloaded = await s3.get(url.json()["url"])
    assert downloaded.content == PDF

    terminated = await client.post(f"{path}/terminate", headers=admin)
    assert terminated.json()["status"] == "TERMINATED"


async def test_upload_rejects_non_pdf_content(client: AsyncClient, admin: dict[str, str]) -> None:
    rejected = await _upload(client, admin, body=b"MZ\x90\x00" + b"0" * 100)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "invalid_contract_file"

    too_long = await client.post(
        f"{API}/contract-files/uploads", json={"file_name": "가" * 97 + ".pdf"}, headers=admin
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "file_name_too_long"


async def test_draft_delete_and_list(client: AsyncClient, admin: dict[str, str]) -> None:
    first = (
        await client.post(f"{API}/contracts", json=await _contract_body(), headers=admin)
    ).json()
    await client.post(
        f"{API}/contracts",
        json=await _contract_body(contractor_name="박강사", educator_type="INSTRUCTOR"),
        headers=admin,
    )

    listed = await client.get(
        f"{API}/contracts", params={"q": "박강", "status": ["DRAFT"]}, headers=admin
    )
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["contractor_name"] == "박강사"

    assert (await client.delete(f"{API}/contracts/{first['id']}", headers=admin)).status_code == 204
    assert (await client.get(f"{API}/contracts/{first['id']}", headers=admin)).status_code == 404


async def test_permissions(client: AsyncClient, settings: Settings, s3_bucket: str) -> None:
    assert (await client.get(f"{API}/contracts")).status_code == 401
    assistant = await _staff(settings, ASSISTANT)
    assert (await client.get(f"{API}/contracts", headers=assistant)).status_code == 403
    # 계약은 기수 범위가 없어 매니저 역할이 하나라도 있으면 허용한다 (A16)
    manager = await _staff(settings, MANAGER)
    assert (await client.get(f"{API}/contracts", headers=manager)).status_code == 200


async def test_validation_errors(client: AsyncClient, admin: dict[str, str]) -> None:
    unknown_employee = await client.post(
        f"{API}/contracts",
        json=await _contract_body(manager_employee_id="00000000-0000-7000-8000-000000000000"),
        headers=admin,
    )
    assert unknown_employee.status_code == 404
    assert unknown_employee.json()["error"]["code"] == "employee_not_found"
    reversed_period = await client.post(
        f"{API}/contracts",
        json=await _contract_body(start_date="2026-02-01", end_date="2026-01-31"),
        headers=admin,
    )
    assert reversed_period.json()["error"]["code"] == "invalid_contract_period"


async def test_link_and_unlink(client: AsyncClient, admin: dict[str, str]) -> None:
    contract = (
        await client.post(f"{API}/contracts", json=await _contract_body(), headers=admin)
    ).json()
    path = f"{API}/contracts/{contract['id']}/link"
    mentor = await create_mentor()
    instructor = await create_instructor()

    linked = await client.post(path, json={"mentor_id": str(mentor.id)}, headers=admin)
    assert linked.status_code == 200, linked.text
    assert linked.json()["mentor_id"] == str(mentor.id)

    wrong = await client.post(path, json={"instructor_id": str(instructor.id)}, headers=admin)
    assert wrong.json()["error"]["code"] == "contract_type_mismatch"
    both = await client.post(
        path,
        json={"mentor_id": str(mentor.id), "instructor_id": str(instructor.id)},
        headers=admin,
    )
    assert both.json()["error"]["code"] == "invalid_contract_link"

    unlinked = await client.delete(path, headers=admin)
    assert unlinked.json()["mentor_id"] is None

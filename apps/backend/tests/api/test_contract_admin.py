"""계약·계약서 관리 API (실제 DB + S3 에뮬레이터 floci, A109)."""

import uuid
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
from tests.factories.access import ASSISTANT, MANAGER, give_role
from tests.factories.educator import create_instructor, create_mentor, mentor_contract_fields
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


async def _staff(settings: Settings, role: str, cohort_id: uuid.UUID) -> dict[str, str]:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await give_role(user.id, role, cohort_id=cohort_id)
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
    fields = await mentor_contract_fields()
    body: dict[str, Any] = {
        "contract_type": "MENTOR",
        "bootcamp_id": str(fields["bootcamp_id"]),
        "cohort_id": str(fields["cohort_id"]),
        "contractor_name": "김멘토",
        "contractor_phone": "010-1234-5678",
        "contractor_email": "Mentor@Example.com",
        "title": "2026 멘토 계약",
        "start_date": "2026-01-01",
        "end_date": "2099-12-31",
        "settlement_type": "UNIT_PRICE",
        "unit_price": 50000,
        "price_unit": "HOURLY",
        "no_show_pay_amount": 10000,
        "mentoring_time_basis": "ACTUAL_DURATION",
        "manager_employee_id": str((await create_employee()).id),
    }
    body.update(overrides)
    return body


def _vendor(body: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    vendor = {
        **body,
        "contract_type": "SW",
        "contractor_name": "(주)오즈",
        "contractor_phone": "02-123-4567",
        "business_registration_number": "123-45-67890",
        "settlement_type": "FIXED",
        "total_amount": 1200000,
        "unit_price": None,
        "price_unit": None,
        "no_show_pay_amount": None,
        "mentoring_time_basis": None,
        "vat_type": "EXCLUDED",
        "cohort_id": None,
    }
    vendor.update(overrides)
    return vendor


async def test_contract_lifecycle(client: AsyncClient, admin: dict[str, str]) -> None:
    created = await client.post(f"{API}/contracts", json=await _contract_body(), headers=admin)
    assert created.status_code == 201, created.text
    contract = created.json()
    assert (contract["status"], contract["contract_file"]) == ("DRAFT", None)
    assert (contract["contractor_phone"], contract["contractor_email"]) == (
        "01012345678",
        "mentor@example.com",
    )
    assert contract["bootcamp_name"]
    assert contract["cohort_number"] == 1
    path = f"{API}/contracts/{contract['id']}"

    no_file = await client.post(f"{path}/progress", headers=admin)
    assert no_file.status_code == 422
    assert no_file.json()["error"]["code"] == "contract_file_required"

    file = await _upload(client, admin)
    assert file.status_code == 201, file.text
    assert (file.json()["file_name"], file.json()["file_size"]) == ("멘토 계약서.pdf", len(PDF))
    attached = await client.patch(path, json={"contract_file_id": file.json()["id"]}, headers=admin)
    assert attached.json()["contract_file"]["id"] == file.json()["id"]

    progressing = await client.post(f"{path}/progress", headers=admin)
    assert progressing.json()["status"] == "IN_PROGRESS"
    signed = await client.post(f"{path}/sign", headers=admin)
    assert signed.json()["status"] == "ACTIVE"
    locked = await client.patch(path, json={"title": "변경"}, headers=admin)
    assert locked.status_code == 422
    assert locked.json()["error"]["code"] == "contract_not_editable"
    assert (await client.delete(path, headers=admin)).status_code == 422

    amended = await client.post(
        f"{path}/amendments",
        json={"amended_on": "2026-11-09", "reason": "단가 인상", "changes": {"unit_price": 60000}},
        headers=admin,
    )
    assert amended.status_code == 201, amended.text
    assert (amended.json()["before"], amended.json()["after"]) == (
        {"unit_price": 50000},
        {"unit_price": 60000},
    )
    assert amended.json()["created_by_name"]
    history = await client.get(f"{path}/amendments", headers=admin)
    assert [a["reason"] for a in history.json()] == ["단가 인상"]
    assert (await client.get(path, headers=admin)).json()["unit_price"] == 60000
    not_amendable = await client.post(
        f"{path}/amendments",
        json={"amended_on": "2026-11-09", "reason": "기수", "changes": {"cohort_id": None}},
        headers=admin,
    )
    # 기수는 변경 계약 항목이 아니라 받지 않는다 → 바뀐 것이 없음
    assert not_amendable.json()["error"]["code"] == "amendment_no_changes"

    url = await client.get(f"{path}/file-url", headers=admin)
    assert url.status_code == 200
    async with httpx.AsyncClient(timeout=10) as s3:
        downloaded = await s3.get(url.json()["url"])
    assert downloaded.content == PDF

    terminated = await client.post(
        f"{path}/terminate",
        json={"reason": "TERMINATED_BY_MUTUAL_AGREEMENT", "detail": "합의 해지"},
        headers=admin,
    )
    assert terminated.json()["status"] == "TERMINATED"
    assert terminated.json()["termination_reason"] == "TERMINATED_BY_MUTUAL_AGREEMENT"
    assert terminated.json()["terminated_on"] is not None


async def test_vendor_contract_and_cancel(client: AsyncClient, admin: dict[str, str]) -> None:
    body = _vendor(await _contract_body())
    created = await client.post(f"{API}/contracts", json=body, headers=admin)
    assert created.status_code == 201, created.text
    contract = created.json()
    assert (contract["contract_type"], contract["mentor_id"], contract["cohort_id"]) == (
        "SW",
        None,
        None,
    )
    assert (contract["contractor_phone"], contract["business_registration_number"]) == (
        "021234567",
        "1234567890",
    )
    canceled = await client.post(
        f"{API}/contracts/{contract['id']}/cancel", json={"reason": "견적 불일치"}, headers=admin
    )
    assert canceled.json()["status"] == "CANCELED"
    assert canceled.json()["cancel_reason"] == "견적 불일치"


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
    instructor = await _contract_body(
        contractor_name="박강사",
        contract_type="INSTRUCTOR",
        no_show_pay_amount=None,
        mentoring_time_basis=None,
    )
    second = await client.post(f"{API}/contracts", json=instructor, headers=admin)
    assert second.status_code == 201, second.text

    listed = await client.get(
        f"{API}/contracts", params={"q": "박강", "status": ["DRAFT"]}, headers=admin
    )
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["contractor_name"] == "박강사"
    by_type = await client.get(
        f"{API}/contracts", params={"contract_type": ["INSTRUCTOR", "SW"]}, headers=admin
    )
    assert [c["id"] for c in by_type.json()["items"]] == [second.json()["id"]]
    by_cohort = await client.get(
        f"{API}/contracts", params={"cohort_id": first["cohort_id"]}, headers=admin
    )
    assert [c["id"] for c in by_cohort.json()["items"]] == [first["id"]]

    assert (await client.delete(f"{API}/contracts/{first['id']}", headers=admin)).status_code == 204
    assert (await client.get(f"{API}/contracts/{first['id']}", headers=admin)).status_code == 404


async def test_permissions_follow_assigned_scope(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    """담당 범위 (A109⑦): 담당 기수의 계약만 보이고, 범위 밖은 404·403."""
    assert (await client.get(f"{API}/contracts")).status_code == 401
    mine_body = await _contract_body()
    other_body = await _contract_body()
    mine = (await client.post(f"{API}/contracts", json=mine_body, headers=admin)).json()
    other = (await client.post(f"{API}/contracts", json=other_body, headers=admin)).json()
    cohort_id = uuid.UUID(mine["cohort_id"])

    assistant = await _staff(settings, ASSISTANT, cohort_id)
    assert (await client.get(f"{API}/contracts", headers=assistant)).status_code == 403

    manager = await _staff(settings, MANAGER, cohort_id)
    listed = await client.get(f"{API}/contracts", headers=manager)
    assert [c["id"] for c in listed.json()["items"]] == [mine["id"]]
    assert (await client.get(f"{API}/contracts/{other['id']}", headers=manager)).status_code == 404
    # 담당 기수가 아닌 곳에는 만들 수 없다
    outside = await client.post(f"{API}/contracts", json=await _contract_body(), headers=manager)
    assert outside.status_code == 403
    inside = await client.post(
        f"{API}/contracts",
        json={
            **await _contract_body(),
            "bootcamp_id": mine["bootcamp_id"],
            "cohort_id": mine["cohort_id"],
        },
        headers=manager,
    )
    assert inside.status_code == 201, inside.text


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
    other = await _contract_body()
    mismatch = await client.post(
        f"{API}/contracts",
        json=await _contract_body(cohort_id=other["cohort_id"]),
        headers=admin,
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "cohort_not_in_bootcamp"
    monthly_mentor = await client.post(
        f"{API}/contracts", json=await _contract_body(price_unit="MONTHLY"), headers=admin
    )
    assert monthly_mentor.json()["error"]["code"] == "invalid_mentor_contract_terms"


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

    # 멘토 계약은 연결을 해제할 수 없다 (A104)
    unlinked = await client.delete(path, headers=admin)
    assert unlinked.json()["error"]["code"] == "mentor_contract_unlink_forbidden"

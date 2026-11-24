"""운영진 가입 신청 검토 API (실제 DB + 실제 서비스 조립)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.registration import RequestedAssignment
from app.contexts.organization.infrastructure.repositories import TortoiseCohortStaffRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.access import ASSISTANT, give_role
from tests.factories.organization import create_department, create_team
from tests.factories.staff_review import create_applicant, create_registration

pytestmark = pytest.mark.api

URL = "/api/v1/admin/staff-registrations"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_list_pending_registrations_with_applicant(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    first = await create_applicant(name="김오즈")
    await create_registration(first)
    await create_registration(await create_applicant())

    response = await client.get(URL, params={"limit": 1}, headers=admin_headers)

    assert response.status_code == 200
    page = response.json()
    assert (page["total"], page["limit"], page["offset"]) == (2, 1, 0)
    assert page["items"][0]["applicant"]["name"] == "김오즈"
    assert page["items"][0]["status"] == "PENDING"


async def test_approve_with_adjustment_then_applicant_has_roles(
    client: AsyncClient, admin_headers: dict[str, str], settings: Settings
) -> None:
    cohort = await create_cohort()
    applicant = await create_applicant()
    registration = await create_registration(applicant, [RequestedAssignment(cohort_id=cohort.id)])
    department = await create_department()
    team = await create_team(department.id)

    response = await client.post(
        f"{URL}/{registration.id}/approve",
        json={
            "department_id": str(department.id),
            "team_id": str(team.id),
            "assignments": [{"cohort_id": str(cohort.id)}],
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert (body["department_id"], body["team_id"]) == (str(department.id), str(team.id))
    assert body["applicant"]["approval_status"] == "APPROVED"
    me = (await client.get("/api/v1/me", headers=bearer(settings, applicant))).json()
    assert me["approval_status"] == "APPROVED"
    # 권한은 직위가, 데이터 범위는 담당이 정한다 (A87): 조정한 기수 담당이 생긴다
    staffs = await TortoiseCohortStaffRepository().list_by_cohort(cohort.id)
    assert len(staffs) == 1


async def test_approve_without_body_uses_requested_values(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    registration = await create_registration(await create_applicant())
    response = await client.post(f"{URL}/{registration.id}/approve", headers=admin_headers)
    assert response.status_code == 200
    assert (response.json()["department_id"], response.json()["team_id"]) == (
        str(registration.department_id),
        None,
    )


async def test_reject_then_applicant_can_see_reason(
    client: AsyncClient, admin_headers: dict[str, str], settings: Settings
) -> None:
    applicant = await create_applicant()
    registration = await create_registration(applicant)

    response = await client.post(
        f"{URL}/{registration.id}/reject",
        json={"reason": "담당 기수 확인 필요"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["applicant"]["approval_status"] == "REJECTED"
    mine = await client.get("/api/v1/me/staff-registration", headers=bearer(settings, applicant))
    assert (mine.json()["status"], mine.json()["reject_reason"]) == (
        "REJECTED",
        "담당 기수 확인 필요",
    )


async def test_review_errors(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    registration = await create_registration(await create_applicant())
    assert (
        await client.post(f"{URL}/{new_id()}/approve", headers=admin_headers)
    ).status_code == 404
    assert (
        await client.post(
            f"{URL}/{registration.id}/reject", json={"reason": ""}, headers=admin_headers
        )
    ).status_code == 422
    await client.post(f"{URL}/{registration.id}/approve", headers=admin_headers)
    again = await client.post(f"{URL}/{registration.id}/approve", headers=admin_headers)
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "registration_not_pending"


async def test_only_super_admin_can_review(client: AsyncClient, settings: Settings) -> None:
    await create_super_admin("boss@nextrunners.co.kr", settings=settings)  # 역할 시드
    cohort = await create_cohort()
    assistant = await create_applicant()
    users = TortoiseUserRepository()
    approved = await users.get(assistant.id)
    assert approved is not None
    approved.approve(now=datetime.now(UTC))
    await users.save(approved)
    await give_role(assistant.id, ASSISTANT, cohort_id=cohort.id)
    pending = await create_applicant()

    forbidden = await client.get(URL, headers=bearer(settings, approved))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "permission_denied"
    gated = await client.get(URL, headers=bearer(settings, pending))
    assert gated.json()["error"]["code"] == "approval_required"
    assert (await client.get(URL)).status_code == 401

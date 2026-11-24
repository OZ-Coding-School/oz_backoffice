"""직원 수정에서 담당 지정 (decisions A89): 직위의 담당 방식, 기수 중복, 권한 나눔 (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.enums import AssignmentScope
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import give_permissions
from tests.factories.organization import create_employee, create_position
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_assignments_follow_position_scope(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    course = await create_position("과정 담당", assignment_scope=AssignmentScope.COURSE)
    cohort_pos = await create_position("기수 담당", assignment_scope=AssignmentScope.COHORT)
    a, b = await create_cohort(), await create_cohort()
    employee = await create_employee()
    url = f"/api/v1/admin/employees/{employee.id}"

    async def patch(body: dict[str, object]) -> tuple[int, object]:
        res = await client.patch(url, json=body, headers=admin)
        data = res.json()
        return res.status_code, data.get("error", {}).get("code") or [
            (x["bootcamp_id"], x["cohort_id"]) for x in data["assignments"]
        ]

    ok = await patch(
        {
            "position_id": str(course.id),
            "bootcamp_ids": [str(a.bootcamp_id), str(b.bootcamp_id)],
        }
    )
    assert ok == (200, [(str(a.bootcamp_id), None), (str(b.bootcamp_id), None)])
    assert await patch({"cohort_ids": [str(a.id)]}) == (422, "invalid_staff_assignment")

    # 기수 담당 직위로 바꾸며 기수 하나로 교체 (과정 담당은 비운다)
    moved = await patch(
        {"position_id": str(cohort_pos.id), "bootcamp_ids": [], "cohort_ids": [str(a.id)]}
    )
    assert moved == (200, [(None, str(a.id))])
    assert await patch({"cohort_ids": [str(a.id), str(b.id)]}) == (422, "invalid_staff_assignment")

    # 다른 직원이 담당한 기수는 고를 수 없다 (A63)
    other = await create_employee()
    await client.patch(
        f"/api/v1/admin/employees/{other.id}",
        json={"position_id": str(cohort_pos.id)},
        headers=admin,
    )
    taken = await client.patch(
        f"/api/v1/admin/employees/{other.id}", json={"cohort_ids": [str(a.id)]}, headers=admin
    )
    assert taken.json()["error"]["code"] == "invalid_staff_assignment"
    # 담당 해제
    assert await patch({"cohort_ids": []}) == (200, [])


async def test_permissions_are_split_by_field(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    course = await create_position("과정 담당", assignment_scope=AssignmentScope.COURSE)
    cohort = await create_cohort()
    employee = await create_employee()
    await client.patch(
        f"/api/v1/admin/employees/{employee.id}",
        json={"position_id": str(course.id)},
        headers=admin,
    )
    url = f"/api/v1/admin/employees/{employee.id}"

    assigner = await create_applicant()
    assigner.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(assigner)
    await give_permissions(
        assigner.id, {"org.employee.read", "staff.assignment.read", "staff.assignment.manage"}
    )
    headers = bearer(settings, assigner)
    ok = await client.patch(url, json={"bootcamp_ids": [str(cohort.bootcamp_id)]}, headers=headers)
    assert ok.status_code == 200
    denied = await client.patch(url, json={"employment_type": "INTERN"}, headers=headers)
    assert denied.status_code == 403

    editor = await create_applicant()
    editor.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(editor)
    await give_permissions(editor.id, {"org.employee.read", "org.employee.manage"})
    headers = bearer(settings, editor)
    assert (
        await client.patch(url, json={"employment_type": "INTERN"}, headers=headers)
    ).status_code == 200
    assert (await client.patch(url, json={"bootcamp_ids": []}, headers=headers)).status_code == 403

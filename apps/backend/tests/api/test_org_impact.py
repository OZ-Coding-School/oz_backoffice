"""부서·팀·직위 영향 조회 (decisions A93): 직원·운영진 가입 신청·팀·담당 과정 (실제 DB)."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.infrastructure.repositories import (
    TortoiseEmployeeRegistrationRepository,
    TortoiseEmployeeRepository,
)
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.access import give_permissions
from tests.factories.organization import create_employee, create_team
from tests.factories.staff_review import create_applicant, create_registration

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def test_team_department_position_impact(client: AsyncClient, admin: dict[str, str]) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    team = await create_team(employee.department_id, "교육 1팀", bootcamp_ids=(cohort.bootcamp_id,))
    employee.transfer(
        department_id=employee.department_id, team_id=team.id, position_id=employee.position_id
    )
    await TortoiseEmployeeRepository().save(employee)
    applicant = await create_applicant(name="신청자")
    registration = await create_registration(applicant)
    registration.department_id = employee.department_id
    registration.team_id = team.id
    registration.position_id = employee.position_id
    await TortoiseEmployeeRegistrationRepository().save(registration)

    by_team = (await client.get(f"/api/v1/admin/teams/{team.id}/impact", headers=admin)).json()
    (row,) = by_team["employees"]
    assert (row["id"], row["team_name"]) == (str(employee.id), "교육 1팀")
    assert all(row[k] for k in ("department_name", "position_name", "email"))
    assert [(r["applicant_name"], r["status"]) for r in by_team["registrations"]] == [
        ("신청자", "PENDING")
    ]
    assert [b["id"] for b in by_team["bootcamps"]] == [str(cohort.bootcamp_id)]
    assert by_team["teams"] == []

    url = f"/api/v1/admin/departments/{employee.department_id}/impact"
    by_department = (await client.get(url, headers=admin)).json()
    assert [t["name"] for t in by_department["teams"]] == ["교육 1팀"]
    assert by_department["teams"][0]["employee_count"] == 1
    assert len(by_department["employees"]) == len(by_department["registrations"]) == 1

    url = f"/api/v1/admin/positions/{employee.position_id}/impact"
    by_position = (await client.get(url, headers=admin)).json()
    assert [e["id"] for e in by_position["employees"]] == [str(employee.id)]

    missing = await client.get(f"/api/v1/admin/teams/{cohort.id}/impact", headers=admin)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "team_not_found")


async def test_impact_permissions(client: AsyncClient, settings: Settings) -> None:
    employee = await create_employee()
    team = await create_team(employee.department_id)
    viewer = await create_applicant()
    viewer.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(viewer)
    await give_permissions(
        viewer.id, {"org.department.read", "access.role.read", "access.role.manage"}
    )
    headers = bearer(settings, viewer)
    # 부서·팀 영향은 부서 관리 권한이 있어야 한다
    assert (
        await client.get(f"/api/v1/admin/teams/{team.id}/impact", headers=headers)
    ).status_code == 403
    # 직위 영향은 권한 관리(권한 화면 저장 확인)로도 볼 수 있다
    assert (
        await client.get(f"/api/v1/admin/positions/{employee.position_id}/impact", headers=headers)
    ).status_code == 200

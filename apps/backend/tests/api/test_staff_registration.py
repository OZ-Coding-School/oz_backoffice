from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.registration_service import StaffRegistrationService
from app.contexts.organization.domain.entities import (
    BootcampTeam,
    Department,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope
from app.contexts.organization.presentation.dependencies import get_staff_registration_service
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.identity import InMemoryUserRepository
from tests.fakes.organization import (
    FakeStaffTargetCatalog,
    InMemoryBootcampTeamRepository,
    InMemoryCohortStaffRepository,
    InMemoryDepartmentRepository,
    InMemoryEmployeePositionRepository,
    InMemoryEmployeeRegistrationRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.api

URL = "/api/v1/me/staff-registration"
DEPARTMENT = Department(name="교육운영본부", description="교육 운영")
TEAM = Team(department_id=DEPARTMENT.id, name="교육 1팀")
OTHER_TEAM = Team(department_id=new_id(), name="다른 팀")
POSITION = EmployeePosition(name="운영 매니저", priority=3, assignment_scope=AssignmentScope.COURSE)
BOOTCAMP = Bootcamp(hrd_net_bootcamp_id=new_id(), name="백엔드", code="AH")
COHORT = Cohort(
    hrd_net_cohort_id=new_id(),
    bootcamp_id=BOOTCAMP.id,
    cohort_number=3,
    start_date=date(2026, 11, 1),
    end_date=date(2027, 4, 30),
)


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def registration_app(app: FastAPI, users: InMemoryUserRepository) -> FastAPI:
    app.state.user_queries = UserQueries(users)
    service = StaffRegistrationService(
        registrations=InMemoryEmployeeRegistrationRepository(),
        departments=InMemoryDepartmentRepository(DEPARTMENT),
        teams=InMemoryTeamRepository(TEAM, OTHER_TEAM),
        bootcamp_teams=InMemoryBootcampTeamRepository(
            BootcampTeam(bootcamp_id=BOOTCAMP.id, team_id=TEAM.id)
        ),
        positions=InMemoryEmployeePositionRepository(POSITION),
        cohort_staffs=InMemoryCohortStaffRepository(),
        catalog=FakeStaffTargetCatalog([BOOTCAMP], [COHORT]),
        uow=FakeUnitOfWork(),
        staff_email_domain="nextrunners.co.kr",
    )
    app.dependency_overrides[get_staff_registration_service] = lambda: service
    return app


@pytest.fixture
async def api(registration_app: FastAPI, client: AsyncClient) -> AsyncClient:
    return client


async def login_as(users: InMemoryUserRepository, settings: Settings, user: User) -> dict[str, str]:
    await users.add(user)
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


def body(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "department_id": str(DEPARTMENT.id),
        "team_id": str(TEAM.id),
        "position_id": str(POSITION.id),
        "employment_type": "REGULAR",
        "assignments": [{"bootcamp_id": str(BOOTCAMP.id)}],
    }
    values.update(overrides)
    return values


@pytest.fixture
async def pending_staff(users: InMemoryUserRepository, settings: Settings) -> dict[str, str]:
    return await login_as(users, settings, make_user(email="kim@nextrunners.co.kr"))


async def test_pending_staff_gets_options(api: AsyncClient, pending_staff: dict[str, str]) -> None:
    response = await api.get(f"{URL}/options", headers=pending_staff)
    assert response.status_code == 200
    options = response.json()
    assert options["departments"] == [{"id": str(DEPARTMENT.id), "name": "교육운영본부"}]
    assert {"id": str(TEAM.id), "department_id": str(DEPARTMENT.id), "name": "교육 1팀"} in (
        options["teams"]
    )
    assert options["positions"] == [
        {"id": str(POSITION.id), "name": "운영 매니저", "assignment_scope": "COURSE"}
    ]
    assert options["bootcamps"][0] == {
        "id": str(BOOTCAMP.id),
        "name": "백엔드",
        "code": "AH",
        "team_id": str(TEAM.id),
    }
    assert options["cohorts"][0]["cohort_number"] == 3
    assert "REGULAR" in options["employment_types"]
    assert "staff_roles" not in options  # 담당 역할 없음 (A89)


async def test_submit_update_and_read_registration(
    api: AsyncClient, pending_staff: dict[str, str]
) -> None:
    assert (await api.get(URL, headers=pending_staff)).json() is None

    created = await api.put(URL, json=body(), headers=pending_staff)
    assert created.status_code == 200
    assert created.json()["status"] == "PENDING"
    assert created.json()["team_id"] == str(TEAM.id)
    assert len(created.json()["assignments"]) == 1

    updated = await api.put(
        URL, json=body(employment_type="CONTRACT", assignments=[]), headers=pending_staff
    )
    assert updated.json()["id"] == created.json()["id"]

    mine = (await api.get(URL, headers=pending_staff)).json()
    assert (mine["employment_type"], mine["assignments"]) == ("CONTRACT", [])


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        (body(assignments=[{"role": "MANAGER"}]), 422, "invalid_staff_assignment"),
        (
            body(assignments=[{"cohort_id": str(new_id())}]),
            422,
            "invalid_staff_target",
        ),
        (body(department_id=str(new_id())), 422, "department_not_found"),
        (body(team_id=str(OTHER_TEAM.id), assignments=[]), 422, "team_not_in_department"),
        (
            body(assignments=[{"cohort_id": str(COHORT.id)}]),
            422,
            "invalid_staff_assignment",
        ),
        (body(employment_type="UNKNOWN"), 422, None),
    ],
)
async def test_submit_validation(
    api: AsyncClient,
    pending_staff: dict[str, str],
    payload: dict[str, object],
    status: int,
    code: str | None,
) -> None:
    response = await api.put(URL, json=payload, headers=pending_staff)
    assert response.status_code == status
    if code:
        assert response.json()["error"]["code"] == code


async def test_non_staff_account_is_forbidden(
    api: AsyncClient, users: InMemoryUserRepository, settings: Settings
) -> None:
    headers = await login_as(users, settings, make_user(email="student@gmail.com"))
    response = await api.put(URL, json=body(), headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_staff_account"


async def test_approved_staff_cannot_resubmit(
    api: AsyncClient, users: InMemoryUserRepository, settings: Settings
) -> None:
    user = make_user(email="lee@nextrunners.co.kr")
    user.approve(now=datetime.now(UTC))
    headers = await login_as(users, settings, user)
    response = await api.put(URL, json=body(), headers=headers)
    assert response.status_code == 409


async def test_requires_login(api: AsyncClient) -> None:
    response = await api.get(URL)
    assert response.status_code == 401

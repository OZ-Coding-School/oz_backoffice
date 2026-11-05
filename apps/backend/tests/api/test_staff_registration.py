from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.registration_service import StaffRegistrationService
from app.contexts.organization.domain.entities import Department, EmployeePosition
from app.contexts.organization.presentation.dependencies import get_staff_registration_service
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.identity import InMemoryUserRepository
from tests.fakes.organization import (
    FakeStaffTargetCatalog,
    InMemoryDepartmentRepository,
    InMemoryEmployeePositionRepository,
    InMemoryEmployeeRegistrationRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.api

URL = "/api/v1/me/staff-registration"
DEPARTMENT = Department(name="교육 1팀", description="부트캠프 운영")
POSITION = EmployeePosition(name="매니저", priority=3)
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
        positions=InMemoryEmployeePositionRepository(POSITION),
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
        "position_id": str(POSITION.id),
        "employment_type": "REGULAR",
        "assignments": [
            {"role": "MANAGER", "bootcamp_id": str(BOOTCAMP.id)},
            {"role": "ASSISTANT", "cohort_id": str(COHORT.id)},
        ],
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
    assert options["departments"] == [
        {"id": str(DEPARTMENT.id), "parent_id": None, "name": "교육 1팀"}
    ]
    assert options["positions"] == [{"id": str(POSITION.id), "name": "매니저"}]
    assert options["bootcamps"][0]["code"] == "AH"
    assert options["cohorts"][0]["cohort_number"] == 3
    assert "REGULAR" in options["employment_types"]
    assert options["staff_roles"] == ["MANAGER", "ASSISTANT"]


async def test_submit_update_and_read_registration(
    api: AsyncClient, pending_staff: dict[str, str]
) -> None:
    assert (await api.get(URL, headers=pending_staff)).json() is None

    created = await api.put(URL, json=body(), headers=pending_staff)
    assert created.status_code == 200
    assert created.json()["status"] == "PENDING"
    assert len(created.json()["assignments"]) == 2

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
            body(assignments=[{"role": "ASSISTANT", "cohort_id": str(new_id())}]),
            422,
            "invalid_staff_target",
        ),
        (body(department_id=str(new_id())), 422, "department_not_found"),
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

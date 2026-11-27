"""GET /me/staff-access (decisions F17·A81, BE-3)."""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.contexts.academy.application.catalog import CohortSummary
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.access.application.permissions import StaffGrant
from app.contexts.access.domain.catalog import DEV_POSITION_PERMISSIONS, PERMISSIONS
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.enums import AccountType
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.access import FakeGrantSource
from tests.fakes.identity import InMemoryUserRepository

pytestmark = pytest.mark.api

NOW = datetime.now(UTC)
URL = "/api/v1/me/staff-access"
BOOTCAMP, OTHER_BOOTCAMP = new_id(), new_id()


def cohort(bootcamp: uuid.UUID, number: int, status: CohortStatus) -> CohortSummary:
    return CohortSummary(
        id=new_id(),
        bootcamp_id=bootcamp,
        bootcamp_name="백엔드" if bootcamp == BOOTCAMP else "프론트엔드",
        cohort_number=number,
        start_date=date(2026, number, 1),
        end_date=date(2026, 12, 31),
        status=status,
    )


C12 = cohort(BOOTCAMP, 11, CohortStatus.ONGOING)
C9 = cohort(OTHER_BOOTCAMP, 9, CohortStatus.ONGOING)
C8 = cohort(OTHER_BOOTCAMP, 8, CohortStatus.ENDED)


class FakeCatalog:
    """기수 → 과정 매핑과 범위 조회 (순서는 넘겨준 목록 순서 그대로)."""

    def __init__(self, cohorts: list[CohortSummary]) -> None:
        self.cohorts = cohorts

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None:
        return next((c.bootcamp_id for c in self.cohorts if c.id == cohort_id), None)

    async def cohorts_in_scope(
        self,
        *,
        all_cohorts: bool,
        bootcamp_ids: Collection[uuid.UUID] = (),
        cohort_ids: Collection[uuid.UUID] = (),
    ) -> list[CohortSummary]:
        return [
            c
            for c in self.cohorts
            if all_cohorts or c.bootcamp_id in bootcamp_ids or c.id in cohort_ids
        ]


@dataclass(frozen=True)
class Position:
    position_id: uuid.UUID
    position_name: str
    all_data: bool


class World:
    def __init__(self, app: FastAPI, settings: Settings) -> None:
        self.users = InMemoryUserRepository()
        self.grants = FakeGrantSource()
        self.positions: dict[uuid.UUID, Position] = {}
        self.settings = settings
        app.state.user_queries = UserQueries(self.users)
        app.state.grant_source = self.grants
        app.state.employee_queries = self
        app.state.academy_catalog = FakeCatalog([C12, C9, C8])

    async def access_of(self, user_id: uuid.UUID) -> "Position | None":
        return self.positions.get(user_id)

    async def login(
        self,
        grant: StaffGrant | None = None,
        *,
        super_admin: bool = False,
        position: str | None = None,
        account_type: AccountType = AccountType.STAFF,
    ) -> dict[str, str]:
        user = make_user(account_type=account_type)
        user.approve(now=NOW)
        if super_admin:
            user.set_super_admin(True)
            grant = StaffGrant(permissions=frozenset(PERMISSIONS), all_data=True)
        await self.users.add(user)
        if grant:
            self.grants.grants[user.id] = grant
        if position:
            self.positions[user.id] = Position(
                new_id(), position, grant.all_data if grant else False
            )
        token, _ = JWTService(self.settings).encode(str(user.id), "access", now=NOW)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(app: FastAPI, settings: Settings) -> World:
    return World(app, settings)


async def test_super_admin_has_every_permission_globally_and_all_cohorts(
    world: World, client: AsyncClient
) -> None:
    headers = await world.login(super_admin=True)
    res = await client.get(URL, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["is_super_admin"], body["position"]) == (True, None)
    assert [p["code"] for p in body["permissions"]] == list(PERMISSIONS)
    assert all(p["is_global"] for p in body["permissions"])
    assert [c["id"] for c in body["cohorts"]] == [str(C12.id), str(C9.id), str(C8.id)]
    assert body["cohorts"][0] == {
        "id": str(C12.id),
        "bootcamp_id": str(BOOTCAMP),
        "bootcamp_name": "백엔드",
        "cohort_number": C12.cohort_number,
        "start_date": C12.start_date.isoformat(),
        "end_date": "2026-12-31",
        "status": "ONGOING",
    }


async def test_assigned_scope_unions_bootcamp_and_cohort(world: World, client: AsyncClient) -> None:
    """데이터 범위 '담당만' 직위 (A87): 기수 엔터티는 담당 과정·기수, 그 밖은 전체."""
    headers = await world.login(
        StaffGrant(
            permissions=DEV_POSITION_PERMISSIONS["운영 매니저"],
            bootcamp_ids=frozenset({OTHER_BOOTCAMP}),
            cohort_ids=frozenset({C12.id}),
        ),
        position="운영 매니저",
    )
    body = (await client.get(URL, headers=headers)).json()
    assert body["position"]["name"] == "운영 매니저"
    assert body["position"]["all_data"] is False
    perms = {p["code"]: p for p in body["permissions"]}
    assert perms["member.approval.manage"] == {
        "code": "member.approval.manage",
        "is_global": False,
        "bootcamp_ids": [str(OTHER_BOOTCAMP)],
        "cohort_ids": [str(C12.id)],
    }
    # 계약도 담당 범위를 따른다 (A109⑦), 기수와 무관한 엔터티는 전체
    assert perms["educator.contract.manage"]["is_global"] is False
    assert perms["educator.mentor.manage"]["is_global"] is True
    assert "org.department.manage" not in perms  # 직위에 없는 권한
    assert "staff.assignment.manage" not in perms
    assert {c["id"] for c in body["cohorts"]} == {str(C12.id), str(C9.id), str(C8.id)}


async def test_staff_without_roles_sees_nothing(world: World, client: AsyncClient) -> None:
    body = (await client.get(URL, headers=await world.login())).json()
    assert body == {"is_super_admin": False, "position": None, "permissions": [], "cohorts": []}


async def test_only_staff(world: World, client: AsyncClient) -> None:
    student = await world.login(account_type=AccountType.STUDENT)
    res = await client.get(URL, headers=student)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "staff_only"
    assert (await client.get(URL)).status_code == 401

from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.contexts.access.application.roles import RoleQueries
from app.contexts.access.domain.catalog import COHORT_ASSISTANT, SUPER_ADMIN
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.core.clock import FixedClock
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.access import FakeCohortDirectory, InMemoryUserRoleRepository
from tests.fakes.identity import InMemoryUserRepository

pytestmark = pytest.mark.api

NOW = datetime.now(UTC)
BOOTCAMP, COHORT, OTHER_COHORT = new_id(), new_id(), new_id()


class World:
    def __init__(self, app: FastAPI, settings: Settings) -> None:
        self.users = InMemoryUserRepository()
        self.user_roles = InMemoryUserRoleRepository()
        self.settings = settings
        app.state.user_queries = UserQueries(self.users)
        app.state.role_queries = RoleQueries(self.user_roles, FixedClock(NOW))
        app.state.academy_catalog = FakeCohortDirectory({COHORT: BOOTCAMP, OTHER_COHORT: new_id()})

    async def login(
        self,
        *,
        approved: bool = True,
        role: str | None = None,
        scope: RoleScopeType = RoleScopeType.GLOBAL,
        scope_id: object = None,
    ) -> dict[str, str]:
        user = make_user(email=f"u{new_id().hex[-12:]}@nextrunners.co.kr")
        if approved:
            user.approve(now=NOW)
        await self.users.add(user)
        if role:
            await self.user_roles.add(
                UserRole(user_id=user.id, role_code=role, scope_type=scope, scope_id=scope_id)  # type: ignore[arg-type]
            )
        token, _ = JWTService(self.settings).encode(str(user.id), "access", now=NOW)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(app: FastAPI, settings: Settings) -> World:
    @app.get("/_test/global")
    async def global_only(
        user: Annotated[User, Depends(require_permission("org.department.manage"))],
    ) -> dict[str, str]:
        return {"email": user.email}

    @app.get("/_test/cohorts/{cohort_id}")
    async def cohort_scoped(
        cohort_id: str,
        user: Annotated[
            User, Depends(require_permission("mentoring.team.manage", cohort_param="cohort_id"))
        ],
    ) -> dict[str, str]:
        return {"cohort_id": cohort_id}

    return World(app, settings)


async def test_global_permission(world: World, client: AsyncClient) -> None:
    admin = await world.login(role=SUPER_ADMIN)
    assistant = await world.login(
        role=COHORT_ASSISTANT, scope=RoleScopeType.COHORT, scope_id=COHORT
    )
    assert (await client.get("/_test/global", headers=admin)).status_code == 200
    denied = await client.get("/_test/global", headers=assistant)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"


async def test_cohort_scoped_permission(world: World, client: AsyncClient) -> None:
    assistant = await world.login(
        role=COHORT_ASSISTANT, scope=RoleScopeType.COHORT, scope_id=COHORT
    )
    assert (await client.get(f"/_test/cohorts/{COHORT}", headers=assistant)).status_code == 200
    assert (
        await client.get(f"/_test/cohorts/{OTHER_COHORT}", headers=assistant)
    ).status_code == 403
    assert (await client.get("/_test/cohorts/not-a-uuid", headers=assistant)).status_code == 404


async def test_pending_user_and_anonymous(world: World, client: AsyncClient) -> None:
    pending = await world.login(approved=False, role=SUPER_ADMIN)
    gated = await client.get("/_test/global", headers=pending)
    assert gated.status_code == 403
    assert gated.json()["error"]["code"] == "approval_required"
    assert (await client.get("/_test/global")).status_code == 401


def test_invalid_declarations_fail_fast() -> None:
    with pytest.raises(ValueError, match="정의되지 않은 권한"):
        require_permission("no.such.permission")
    with pytest.raises(ValueError, match="하나만"):
        require_permission("academy.roster.sync", cohort_param="cohort_id", any_scope=True)

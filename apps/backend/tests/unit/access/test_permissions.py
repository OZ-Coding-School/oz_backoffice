from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.access.application.permissions import PermissionChecker, PermissionTarget
from app.contexts.access.application.roles import RoleQueries
from app.contexts.access.domain.catalog import (
    COHORT_ASSISTANT,
    COHORT_MANAGER,
    STUDENT,
    SUPER_ADMIN,
)
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.core.clock import FixedClock
from app.shared.errors import PermissionDeniedError
from app.shared.ids import new_id
from tests.fakes.access import CountingUserRoleRepository, FakeCohortDirectory

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=UTC)
BOOTCAMP = new_id()
COHORT = new_id()  # BOOTCAMP 소속
OTHER_BOOTCAMP = new_id()
OTHER_COHORT = new_id()  # OTHER_BOOTCAMP 소속


class Harness:
    def __init__(self) -> None:
        self.user_roles = CountingUserRoleRepository()
        self.cohorts = FakeCohortDirectory({COHORT: BOOTCAMP, OTHER_COHORT: OTHER_BOOTCAMP})
        self.checker = PermissionChecker(
            RoleQueries(self.user_roles, FixedClock(NOW)), self.cohorts
        )
        self.user_id = new_id()

    async def grant(
        self, role: str, scope: RoleScopeType, scope_id: object = None, **kw: object
    ) -> None:
        await self.user_roles.add(
            UserRole(
                user_id=self.user_id,
                role_code=role,
                scope_type=scope,
                scope_id=scope_id,  # type: ignore[arg-type]
                **kw,  # type: ignore[arg-type]
            )
        )


@pytest.fixture
def h() -> Harness:
    return Harness()


G = PermissionTarget.global_()
ANY = PermissionTarget.any_scope()


@pytest.mark.parametrize(
    ("role", "scope", "scope_id", "code", "target", "allowed"),
    [
        # SUPER_ADMIN(GLOBAL)은 모든 권한·범위
        (SUPER_ADMIN, RoleScopeType.GLOBAL, None, "org.manage", G, True),
        (
            SUPER_ADMIN,
            RoleScopeType.GLOBAL,
            None,
            "roster.sync",
            PermissionTarget.cohort(OTHER_COHORT),
            True,
        ),
        # 과정 매니저: 그 과정과 소속 기수만
        (
            COHORT_MANAGER,
            RoleScopeType.BOOTCAMP,
            BOOTCAMP,
            "mentoring.settings.manage",
            PermissionTarget.cohort(COHORT),
            True,
        ),
        (
            COHORT_MANAGER,
            RoleScopeType.BOOTCAMP,
            BOOTCAMP,
            "mentoring.settings.manage",
            PermissionTarget.bootcamp(BOOTCAMP),
            True,
        ),
        (
            COHORT_MANAGER,
            RoleScopeType.BOOTCAMP,
            BOOTCAMP,
            "mentoring.settings.manage",
            PermissionTarget.cohort(OTHER_COHORT),
            False,
        ),
        (
            COHORT_MANAGER,
            RoleScopeType.BOOTCAMP,
            BOOTCAMP,
            "mentoring.settings.manage",
            PermissionTarget.bootcamp(OTHER_BOOTCAMP),
            False,
        ),
        (COHORT_MANAGER, RoleScopeType.BOOTCAMP, BOOTCAMP, "mentoring.settings.manage", G, False),
        # 매니저에게 없는 권한
        (
            COHORT_MANAGER,
            RoleScopeType.BOOTCAMP,
            BOOTCAMP,
            "org.manage",
            PermissionTarget.cohort(COHORT),
            False,
        ),
        # 계약 관리는 범위가 없어 매니저 역할이 하나라도 있으면 된다(ANY)
        (COHORT_MANAGER, RoleScopeType.COHORT, COHORT, "contract.manage", ANY, True),
        (COHORT_ASSISTANT, RoleScopeType.COHORT, COHORT, "contract.manage", ANY, False),
        # 기수 조교: 그 기수만, 과정 단위 대상에는 권한 없음
        (
            COHORT_ASSISTANT,
            RoleScopeType.COHORT,
            COHORT,
            "mentoring.team.manage",
            PermissionTarget.cohort(COHORT),
            True,
        ),
        (
            COHORT_ASSISTANT,
            RoleScopeType.COHORT,
            COHORT,
            "mentoring.team.manage",
            PermissionTarget.cohort(OTHER_COHORT),
            False,
        ),
        (
            COHORT_ASSISTANT,
            RoleScopeType.COHORT,
            COHORT,
            "mentoring.team.manage",
            PermissionTarget.bootcamp(BOOTCAMP),
            False,
        ),
        (
            COHORT_ASSISTANT,
            RoleScopeType.COHORT,
            COHORT,
            "mentoring.settlement.close",
            PermissionTarget.cohort(COHORT),
            False,
        ),
        # 수강생 역할에는 권한 코드가 없다 (소유 관계로 검사)
        (
            STUDENT,
            RoleScopeType.COHORT,
            COHORT,
            "mentoring.request.read",
            PermissionTarget.cohort(COHORT),
            False,
        ),
    ],
)
async def test_permission_matrix(
    h: Harness,
    role: str,
    scope: RoleScopeType,
    scope_id: object,
    code: str,
    target: PermissionTarget,
    allowed: bool,
) -> None:
    await h.grant(role, scope, scope_id)
    assert await h.checker.has(h.user_id, code, target) is allowed


async def test_no_roles_means_no_permission(h: Harness) -> None:
    assert not await h.checker.has(h.user_id, "mentoring.request.read", ANY)
    with pytest.raises(PermissionDeniedError) as exc:
        await h.checker.require(h.user_id, "mentoring.request.read", ANY)
    assert exc.value.code == "permission_denied"


async def test_expired_role_is_ignored(h: Harness) -> None:
    await h.grant(SUPER_ADMIN, RoleScopeType.GLOBAL, expires_at=NOW - timedelta(seconds=1))
    assert not await h.checker.has(h.user_id, "org.manage", G)


async def test_unknown_cohort_is_denied_for_scoped_roles(h: Harness) -> None:
    await h.grant(COHORT_MANAGER, RoleScopeType.BOOTCAMP, BOOTCAMP)
    assert not await h.checker.has(
        h.user_id, "mentoring.request.read", PermissionTarget.cohort(new_id())
    )


async def test_roles_are_loaded_once_per_checker(h: Harness) -> None:
    await h.grant(COHORT_ASSISTANT, RoleScopeType.COHORT, COHORT)
    for _ in range(3):
        await h.checker.has(h.user_id, "mentoring.team.manage", PermissionTarget.cohort(COHORT))
    assert h.user_roles.list_calls == 1
    # 기수 권한으로 판정되면 과정 조회를 하지 않는다
    assert h.cohorts.lookups == 0


async def test_unknown_permission_code_is_a_programming_error(h: Harness) -> None:
    with pytest.raises(ValueError, match="정의되지 않은 권한"):
        await h.checker.has(h.user_id, "mentoring.unknown", G)

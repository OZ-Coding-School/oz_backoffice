"""권한 판정 (decisions A86·A87): 직위 권한 + 데이터 범위(전체 / 담당 과정·기수)."""

import pytest

from app.contexts.access.application.permissions import (
    PermissionChecker,
    PermissionScope,
    PermissionTarget,
    StaffGrant,
)
from app.shared.errors import PermissionDeniedError
from app.shared.ids import new_id
from tests.fakes.access import FakeCohortDirectory, FakeGrantSource

pytestmark = pytest.mark.unit

BOOTCAMP = new_id()
COHORT = new_id()  # BOOTCAMP 소속
OTHER_BOOTCAMP = new_id()
OTHER_COHORT = new_id()  # OTHER_BOOTCAMP 소속
G = PermissionTarget.global_()
ANY = PermissionTarget.any_scope()
IN_BOOTCAMP = PermissionTarget.bootcamp(BOOTCAMP)
IN_COHORT = PermissionTarget.cohort(COHORT)
IN_OTHER = PermissionTarget.cohort(OTHER_COHORT)


class Harness:
    def __init__(self, grant: StaffGrant) -> None:
        self.source = FakeGrantSource()
        self.cohorts = FakeCohortDirectory({COHORT: BOOTCAMP, OTHER_COHORT: OTHER_BOOTCAMP})
        self.user_id = new_id()
        self.source.grants[self.user_id] = grant
        self.checker = PermissionChecker(self.source, self.cohorts)

    async def has(self, code: str, target: PermissionTarget) -> bool:
        return await self.checker.has(self.user_id, code, target)


READ = "mentoring.request.read"  # 기수에 속한 엔터티
ORG = "org.department.manage"  # 기수와 무관한 엔터티


async def test_without_permission_nothing_is_allowed() -> None:
    h = Harness(StaffGrant(permissions=frozenset({ORG}), all_data=True))
    assert not await h.has(READ, IN_COHORT)
    assert not await h.has(READ, ANY)
    assert (await h.checker.scope_of(h.user_id, READ)).is_empty


async def test_entities_outside_cohorts_ignore_data_scope() -> None:
    """조직·과정·계약 같은 엔터티는 권한만 있으면 된다 (A87)."""
    h = Harness(StaffGrant(permissions=frozenset({ORG})))  # 담당만, 담당 없음
    assert await h.has(ORG, G)
    assert await h.has(ORG, ANY)
    assert (await h.checker.scope_of(h.user_id, ORG)).is_global


async def test_all_data_scope_reaches_every_cohort() -> None:
    h = Harness(StaffGrant(permissions=frozenset({READ}), all_data=True))
    for target in (G, ANY, IN_BOOTCAMP, IN_COHORT, IN_OTHER):
        assert await h.has(READ, target)
    assert (await h.checker.scope_of(h.user_id, READ)).is_global


@pytest.mark.parametrize(
    ("bootcamps", "cohorts", "target", "allowed"),
    [
        ((BOOTCAMP,), (), IN_BOOTCAMP, True),
        ((BOOTCAMP,), (), IN_COHORT, True),  # 과정 담당은 소속 기수 전부
        ((BOOTCAMP,), (), IN_OTHER, False),
        ((), (COHORT,), IN_COHORT, True),
        ((), (COHORT,), IN_BOOTCAMP, False),  # 기수 담당은 과정 전체가 아니다
        ((), (COHORT,), IN_OTHER, False),
        ((BOOTCAMP,), (COHORT,), G, False),  # 전체가 필요한 대상
        ((), (), ANY, True),  # 어느 범위든: 권한만 있으면
        ((), (), IN_COHORT, False),
    ],
)
async def test_assigned_scope_follows_assignments(
    bootcamps: tuple[object, ...],
    cohorts: tuple[object, ...],
    target: PermissionTarget,
    allowed: bool,
) -> None:
    h = Harness(
        StaffGrant(
            permissions=frozenset({READ}),
            bootcamp_ids=frozenset(bootcamps),  # type: ignore[arg-type]
            cohort_ids=frozenset(cohorts),  # type: ignore[arg-type]
        )
    )
    assert await h.has(READ, target) is allowed


async def test_scope_of_assigned_lists_assignments() -> None:
    h = Harness(
        StaffGrant(
            permissions=frozenset({READ}),
            bootcamp_ids=frozenset({OTHER_BOOTCAMP}),
            cohort_ids=frozenset({COHORT}),
        )
    )
    assert await h.checker.scope_of(h.user_id, READ) == PermissionScope(
        bootcamp_ids=frozenset({OTHER_BOOTCAMP}), cohort_ids=frozenset({COHORT})
    )


async def test_grant_is_loaded_once_per_checker() -> None:
    h = Harness(StaffGrant(permissions=frozenset({READ}), cohort_ids=frozenset({COHORT})))
    await h.has(READ, IN_COHORT)
    await h.has(READ, IN_OTHER)
    await h.checker.scope_of(h.user_id, READ)
    assert h.source.calls == 1


async def test_require_and_unknown_code() -> None:
    h = Harness(StaffGrant())
    with pytest.raises(PermissionDeniedError):
        await h.checker.require(h.user_id, READ, IN_COHORT)
    with pytest.raises(ValueError, match="정의되지 않은 권한"):
        await h.has("no.such.permission", G)

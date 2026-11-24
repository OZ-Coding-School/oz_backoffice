"""권한 출처 (A87): 최고 관리자 필드 → 모든 권한, 직원 → 직위 권한·데이터 범위·담당."""

import uuid
from dataclasses import dataclass

import pytest

from app.contexts.access.application.grant_source import StaffGrantSource
from app.contexts.access.application.permissions import NO_GRANT
from app.contexts.access.domain.catalog import PERMISSIONS
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class Access:
    position_id: uuid.UUID
    position_name: str
    permissions: frozenset[str]
    all_data: bool
    bootcamp_ids: frozenset[uuid.UUID]
    cohort_ids: frozenset[uuid.UUID]


class Users:
    def __init__(self, supers: set[uuid.UUID]) -> None:
        self.supers = supers

    async def is_super_admin(self, user_id: uuid.UUID) -> bool:
        return user_id in self.supers


class Employees:
    def __init__(self, access: dict[uuid.UUID, Access]) -> None:
        self.access = access

    async def access_of(self, user_id: uuid.UUID) -> Access | None:
        return self.access.get(user_id)


async def test_super_admin_staff_and_others() -> None:
    admin, staff, student = new_id(), new_id(), new_id()
    cohort = new_id()
    source = StaffGrantSource(
        Users({admin}),
        Employees(
            {
                staff: Access(
                    new_id(),
                    "조교",
                    frozenset({"mentoring.request.read", "retired.code"}),
                    False,
                    frozenset(),
                    frozenset({cohort}),
                )
            }
        ),
    )
    full = await source.grant_of(admin)
    assert (full.permissions, full.all_data) == (frozenset(PERMISSIONS), True)
    grant = await source.grant_of(staff)
    assert grant.permissions == {"mentoring.request.read"}  # 정의에 없는 코드는 버린다
    assert (grant.all_data, grant.cohort_ids) == (False, frozenset({cohort}))
    assert await source.grant_of(student) == NO_GRANT

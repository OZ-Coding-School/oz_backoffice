"""회원 → 권한·데이터 범위 (decisions A87).

최고 관리자 여부는 identity, 직위 권한·데이터 범위·담당 배정은 organization 공개 서비스에서 읽는다.
app.main이 두 서비스를 넣어 만든다(B10).
"""

import uuid
from typing import Protocol

from app.contexts.access.application.permissions import NO_GRANT, StaffGrant
from app.contexts.access.domain.catalog import PERMISSIONS


class SuperAdminDirectory(Protocol):
    """identity `UserQueries`가 구현."""

    async def is_super_admin(self, user_id: uuid.UUID) -> bool: ...


class EmployeeAccess(Protocol):
    @property
    def position_id(self) -> uuid.UUID: ...
    @property
    def position_name(self) -> str: ...
    @property
    def permissions(self) -> frozenset[str]: ...
    @property
    def all_data(self) -> bool: ...
    @property
    def bootcamp_ids(self) -> frozenset[uuid.UUID]: ...
    @property
    def cohort_ids(self) -> frozenset[uuid.UUID]: ...


class EmployeeAccessDirectory(Protocol):
    """organization `EmployeeQueries`가 구현."""

    async def access_of(self, user_id: uuid.UUID) -> EmployeeAccess | None: ...


class StaffGrantSource:
    def __init__(self, users: SuperAdminDirectory, employees: EmployeeAccessDirectory) -> None:
        self._users = users
        self._employees = employees

    async def grant_of(self, user_id: uuid.UUID) -> StaffGrant:
        if await self._users.is_super_admin(user_id):
            return StaffGrant(permissions=frozenset(PERMISSIONS), all_data=True)
        access = await self._employees.access_of(user_id)
        if access is None:
            return NO_GRANT
        return StaffGrant(
            permissions=access.permissions & PERMISSIONS.keys(),
            all_data=access.all_data,
            bootcamp_ids=access.bootcamp_ids,
            cohort_ids=access.cohort_ids,
        )

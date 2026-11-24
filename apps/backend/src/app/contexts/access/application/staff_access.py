"""운영진 유효 권한·담당 기수 조회 (decisions F17·A81, BE-3).

프론트는 이 응답으로 운영진 모듈·메뉴·버튼을 숨기고 '현재 기수' 목록을 만든다.
역할별 권한은 DB 매핑(A84)을 따르고, 최종 판정은 각 API의 권한 검사(403)다.
"""

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.contexts.access.application.permissions import PermissionChecker, PermissionScope
from app.contexts.access.domain.catalog import PERMISSIONS


class ScopedCohort(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def bootcamp_id(self) -> uuid.UUID: ...
    @property
    def bootcamp_name(self) -> str: ...
    @property
    def cohort_number(self) -> int: ...
    @property
    def start_date(self) -> date: ...
    @property
    def end_date(self) -> date: ...
    @property
    def status(self) -> str: ...


class ScopedCohortCatalog(Protocol):
    """academy `AcademyCatalog`가 구현한다."""

    async def cohorts_in_scope(
        self,
        *,
        all_cohorts: bool,
        bootcamp_ids: Collection[uuid.UUID] = (),
        cohort_ids: Collection[uuid.UUID] = (),
    ) -> list[ScopedCohort]: ...


@dataclass(frozen=True, slots=True)
class StaffAccess:
    permissions: dict[str, PermissionScope]  # 가진 권한만, 정의 순서
    cohorts: list[ScopedCohort]


class StaffAccessQueries:
    def __init__(self, checker: PermissionChecker, cohorts: ScopedCohortCatalog) -> None:
        self._checker = checker
        self._cohorts = cohorts

    async def of(self, user_id: uuid.UUID) -> StaffAccess:
        permissions: dict[str, PermissionScope] = {}
        for code in PERMISSIONS:
            scope = await self._checker.scope_of(user_id, code)  # 역할은 요청당 한 번 읽는다
            if not scope.is_empty:
                permissions[code] = scope
        is_global = any(s.is_global for s in permissions.values())
        bootcamps = {b for s in permissions.values() for b in s.bootcamp_ids}
        cohorts = {c for s in permissions.values() for c in s.cohort_ids}
        return StaffAccess(
            permissions=permissions,
            cohorts=await self._cohorts.cohorts_in_scope(
                all_cohorts=is_global, bootcamp_ids=bootcamps, cohort_ids=cohorts
            ),
        )

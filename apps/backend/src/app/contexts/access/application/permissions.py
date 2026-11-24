"""권한 판정 (decisions D4·A86·A87).

- 운영진의 권한은 직위의 권한 묶음이다(직위 = 역할).
  최고 관리자(회원 필드)는 모든 권한·모든 데이터다.
- 데이터 범위는 기수에 속한 엔터티(`cohort_bound`)에만 적용한다. 직위의 데이터 범위가 '전체'면
  모든 기수, '담당만'이면 담당자로 배정된 과정(소속 기수 전부)·기수만이다.
  그 밖의 엔터티는 권한만 있으면 된다.
- 대상 종류: GLOBAL(모든 데이터가 필요), ANY(권한만 있으면), BOOTCAMP·COHORT(그 과정·기수).
- 권한은 요청당 한 번만 읽는다 (PermissionChecker 인스턴스가 요청 단위로 캐시한다).
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.contexts.access.domain.catalog import PERMISSIONS, PERMISSIONS_BY_CODE
from app.shared.errors import PermissionDeniedError


class TargetKind(StrEnum):
    GLOBAL = "GLOBAL"  # 전체 범위 권한이 필요 (예: 조직 관리, 역할 부여)
    ANY = "ANY"  # 어느 범위든 권한이 하나라도 있으면 됨 (예: 계약 관리)
    BOOTCAMP = "BOOTCAMP"
    COHORT = "COHORT"


@dataclass(frozen=True, slots=True)
class PermissionTarget:
    kind: TargetKind
    id: uuid.UUID | None = None

    @classmethod
    def global_(cls) -> "PermissionTarget":
        return cls(TargetKind.GLOBAL)

    @classmethod
    def any_scope(cls) -> "PermissionTarget":
        return cls(TargetKind.ANY)

    @classmethod
    def bootcamp(cls, bootcamp_id: uuid.UUID) -> "PermissionTarget":
        return cls(TargetKind.BOOTCAMP, bootcamp_id)

    @classmethod
    def cohort(cls, cohort_id: uuid.UUID) -> "PermissionTarget":
        return cls(TargetKind.COHORT, cohort_id)


@dataclass(frozen=True, slots=True)
class PermissionScope:
    """권한이 미치는 범위. is_global이면 전체, 아니면 과정·기수 ID 목록."""

    is_global: bool = False
    bootcamp_ids: frozenset[uuid.UUID] = frozenset()
    cohort_ids: frozenset[uuid.UUID] = frozenset()

    @property
    def is_empty(self) -> bool:
        return not (self.is_global or self.bootcamp_ids or self.cohort_ids)


class CohortDirectory(Protocol):
    """기수가 속한 과정 조회 (academy `AcademyCatalog`가 구현)."""

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None: ...


def ensure_known_permission(code: str) -> None:
    if code not in PERMISSIONS:
        raise ValueError(f"정의되지 않은 권한 코드입니다: {code}")


@dataclass(frozen=True, slots=True)
class StaffGrant:
    """한 회원의 권한과 데이터 범위 (A87)."""

    permissions: frozenset[str] = frozenset()
    all_data: bool = False
    bootcamp_ids: frozenset[uuid.UUID] = frozenset()
    cohort_ids: frozenset[uuid.UUID] = frozenset()


NO_GRANT = StaffGrant()


class GrantSource(Protocol):
    """회원 → 권한·데이터 범위 (`StaffGrantSource`가 구현)."""

    async def grant_of(self, user_id: uuid.UUID) -> StaffGrant: ...


class PermissionChecker:
    def __init__(self, grants: GrantSource, cohorts: CohortDirectory) -> None:
        self._source = grants
        self._cohorts = cohorts
        self._grants: dict[uuid.UUID, StaffGrant] = {}

    async def has(self, user_id: uuid.UUID, code: str, target: PermissionTarget) -> bool:
        ensure_known_permission(code)
        grant = await self._grant_of(user_id)
        if code not in grant.permissions:
            return False
        if not PERMISSIONS_BY_CODE[code].cohort_bound or grant.all_data:
            return True
        if target.kind is TargetKind.ANY:
            return True
        if target.kind is TargetKind.GLOBAL or target.id is None:
            return False
        if target.kind is TargetKind.BOOTCAMP:
            return target.id in grant.bootcamp_ids
        # COHORT: 담당 기수, 또는 기수가 속한 담당 과정
        if target.id in grant.cohort_ids:
            return True
        if not grant.bootcamp_ids:
            return False
        return await self._cohorts.bootcamp_id_of(target.id) in grant.bootcamp_ids

    async def scope_of(self, user_id: uuid.UUID, code: str) -> PermissionScope:
        """목록을 담당 범위로 거를 때 쓴다 (예: 승인 대기 목록)."""
        ensure_known_permission(code)
        grant = await self._grant_of(user_id)
        if code not in grant.permissions:
            return PermissionScope()
        if not PERMISSIONS_BY_CODE[code].cohort_bound or grant.all_data:
            return PermissionScope(is_global=True)
        return PermissionScope(bootcamp_ids=grant.bootcamp_ids, cohort_ids=grant.cohort_ids)

    async def require(self, user_id: uuid.UUID, code: str, target: PermissionTarget) -> None:
        if not await self.has(user_id, code, target):
            raise PermissionDeniedError("이 작업을 할 권한이 없습니다.", code="permission_denied")

    async def _grant_of(self, user_id: uuid.UUID) -> StaffGrant:
        if user_id not in self._grants:
            self._grants[user_id] = await self._source.grant_of(user_id)
        return self._grants[user_id]

"""권한 판정 (plan §2.3, decisions D4·M31·A84).

- 역할 → 권한 매핑은 DB `role_permissions`를 따른다(A84). 사용자 역할을 읽을 때 함께 읽는다.
  최고 관리자는 항상 모든 권한이다.
- 범위: GLOBAL은 전체, BOOTCAMP는 그 과정과 소속 기수 전부, COHORT는 그 기수만.
- 사용자 역할은 요청당 한 번만 읽는다 (PermissionChecker 인스턴스가 요청 단위로 캐시한다).
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.contexts.access.application.roles import RoleQueries
from app.contexts.access.domain.catalog import PERMISSIONS
from app.contexts.access.domain.entities import RoleGrant
from app.contexts.access.domain.enums import RoleScopeType
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


class PermissionChecker:
    def __init__(self, roles: RoleQueries, cohorts: CohortDirectory) -> None:
        self._roles = roles
        self._cohorts = cohorts
        self._grants: dict[uuid.UUID, list[RoleGrant]] = {}

    async def has(self, user_id: uuid.UUID, code: str, target: PermissionTarget) -> bool:
        ensure_known_permission(code)
        grants = [g for g in await self._grants_of(user_id) if code in g.permissions]
        if not grants:
            return False
        if target.kind is TargetKind.ANY or any(
            g.scope_type is RoleScopeType.GLOBAL for g in grants
        ):
            return True
        if target.kind is TargetKind.GLOBAL:
            return False
        if target.kind is TargetKind.BOOTCAMP:
            return any(
                g.scope_type is RoleScopeType.BOOTCAMP and g.scope_id == target.id for g in grants
            )
        # COHORT: 그 기수 권한, 또는 기수가 속한 과정의 권한
        if any(g.scope_type is RoleScopeType.COHORT and g.scope_id == target.id for g in grants):
            return True
        bootcamp_scopes = {g.scope_id for g in grants if g.scope_type is RoleScopeType.BOOTCAMP}
        if not bootcamp_scopes or target.id is None:
            return False
        return await self._cohorts.bootcamp_id_of(target.id) in bootcamp_scopes

    async def scope_of(self, user_id: uuid.UUID, code: str) -> PermissionScope:
        """목록을 담당 범위로 거를 때 쓴다 (예: 승인 대기 목록)."""
        ensure_known_permission(code)
        grants = [g for g in await self._grants_of(user_id) if code in g.permissions]
        if any(g.scope_type is RoleScopeType.GLOBAL for g in grants):
            return PermissionScope(is_global=True)
        return PermissionScope(
            bootcamp_ids=frozenset(
                g.scope_id
                for g in grants
                if g.scope_type is RoleScopeType.BOOTCAMP and g.scope_id is not None
            ),
            cohort_ids=frozenset(
                g.scope_id
                for g in grants
                if g.scope_type is RoleScopeType.COHORT and g.scope_id is not None
            ),
        )

    async def require(self, user_id: uuid.UUID, code: str, target: PermissionTarget) -> None:
        if not await self.has(user_id, code, target):
            raise PermissionDeniedError("이 작업을 할 권한이 없습니다.", code="permission_denied")

    async def _grants_of(self, user_id: uuid.UUID) -> list[RoleGrant]:
        if user_id not in self._grants:
            self._grants[user_id] = await self._roles.list_for_user(user_id)
        return self._grants[user_id]

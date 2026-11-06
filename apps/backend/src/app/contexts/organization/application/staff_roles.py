"""담당 역할(StaffRole) ↔ 권한 역할(user_roles) 연결 (decisions D4).

- 매니저 → COHORT_MANAGER, 조교 → COHORT_ASSISTANT
- 범위는 담당 대상: 과정이면 BOOTCAMP, 기수면 COHORT
"""

import uuid
from typing import Protocol

from app.contexts.access.domain.catalog import COHORT_ASSISTANT, COHORT_MANAGER
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.organization.domain.enums import StaffRole

STAFF_ROLE_TO_ROLE_CODE = {StaffRole.MANAGER: COHORT_MANAGER, StaffRole.ASSISTANT: COHORT_ASSISTANT}


def role_scope(
    role: StaffRole, *, bootcamp_id: uuid.UUID | None = None, cohort_id: uuid.UUID | None = None
) -> tuple[str, RoleScopeType, uuid.UUID]:
    """담당 1건에 대응하는 (역할 코드, 범위, 범위 ID). 과정·기수 중 하나만 받는다."""
    if (bootcamp_id is None) == (cohort_id is None):
        raise ValueError("담당 대상은 과정 또는 기수 중 하나여야 합니다.")
    if bootcamp_id is not None:
        return STAFF_ROLE_TO_ROLE_CODE[role], RoleScopeType.BOOTCAMP, bootcamp_id
    assert cohort_id is not None  # noqa: S101 - 위에서 보장
    return STAFF_ROLE_TO_ROLE_CODE[role], RoleScopeType.COHORT, cohort_id


class StaffRoleGranter(Protocol):
    """access `RoleAssignmentService`가 구현."""

    async def grant(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: RoleScopeType,
        scope_id: uuid.UUID | None = None,
    ) -> bool: ...


class StaffRoleSync(StaffRoleGranter, Protocol):
    """부여 + 회수 (access `RoleAssignmentService`가 구현)."""

    async def revoke(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: RoleScopeType,
        scope_id: uuid.UUID | None = None,
    ) -> bool: ...

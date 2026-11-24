from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.access.domain.catalog import (
    COHORT_ASSISTANT,
    COHORT_MANAGER,
    GLOBAL_ONLY_PERMISSIONS,
    LEGACY_PERMISSIONS,
    PERMISSIONS,
    PERMISSIONS_BY_CODE,
    ROLES_BY_CODE,
    STUDENT,
    SUPER_ADMIN,
    TEAM_LEAD,
)
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 6, tzinfo=UTC)


def test_permission_table_matches_plan() -> None:
    """기본 묶음 (A36·A86): 매니저는 조교 권한 + 계약·멘토·설정·배정·정산,
    팀리드는 매니저 + 담당자 + 직원 조회, 최고 관리자는 전부."""
    admin = ROLES_BY_CODE[SUPER_ADMIN].permissions
    manager = ROLES_BY_CODE[COHORT_MANAGER].permissions
    team_lead = ROLES_BY_CODE[TEAM_LEAD].permissions
    assistant = ROLES_BY_CODE[COHORT_ASSISTANT].permissions
    assert admin == set(PERMISSIONS)
    assert assistant < manager < team_lead < admin
    assert team_lead - manager == {
        "staff.assignment.read",
        "staff.assignment.manage",
        "org.employee.read",
    }
    assert {p.rsplit(".", 1)[0] for p in manager - assistant} == {
        "educator.contract",
        "educator.mentor",
        "mentoring.settings",
        "mentoring.assignment",
        "mentoring.settlement",
    }
    assert GLOBAL_ONLY_PERMISSIONS.isdisjoint(manager)
    for role in ROLES_BY_CODE.values():
        assert role.permissions <= set(PERMISSIONS)
        for code in role.permissions:  # 관리·특별 동작은 조회와 함께 (A86)
            needed = PERMISSIONS_BY_CODE[code].requires
            assert needed is None or needed in role.permissions


def test_legacy_codes_map_to_known_permissions() -> None:
    assert len(PERMISSIONS) == 40
    for old, new in LEGACY_PERMISSIONS.items():
        assert new <= set(PERMISSIONS), old
        for code in new:
            needed = PERMISSIONS_BY_CODE[code].requires
            assert needed is None or needed in new, (old, code)


@pytest.mark.parametrize(
    ("role", "scope", "with_id", "valid"),
    [
        (SUPER_ADMIN, RoleScopeType.GLOBAL, False, True),
        (SUPER_ADMIN, RoleScopeType.COHORT, True, False),
        (SUPER_ADMIN, RoleScopeType.GLOBAL, True, False),
        (COHORT_MANAGER, RoleScopeType.BOOTCAMP, True, True),
        (COHORT_ASSISTANT, RoleScopeType.COHORT, True, True),
        (COHORT_MANAGER, RoleScopeType.COHORT, False, False),
        (COHORT_MANAGER, RoleScopeType.GLOBAL, False, False),
        (STUDENT, RoleScopeType.BOOTCAMP, True, False),
        ("CUSTOM_ROLE", RoleScopeType.GLOBAL, False, True),  # 새 역할 범위는 서비스가 검사 (A84)
    ],
)
def test_user_role_scope_rules(role: str, scope: RoleScopeType, with_id: bool, valid: bool) -> None:
    def build() -> UserRole:
        return UserRole(
            user_id=new_id(),
            role_code=role,
            scope_type=scope,
            scope_id=new_id() if with_id else None,
        )

    if valid:
        build()
    else:
        with pytest.raises(BusinessRuleViolation):
            build()


def test_user_role_expiry() -> None:
    temporary = UserRole(
        user_id=new_id(),
        role_code=SUPER_ADMIN,
        scope_type=RoleScopeType.GLOBAL,
        expires_at=NOW + timedelta(hours=1),
    )
    assert temporary.is_effective(NOW)
    assert not temporary.is_effective(NOW + timedelta(hours=1))

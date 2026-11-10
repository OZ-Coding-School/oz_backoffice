from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.access.domain.catalog import (
    COHORT_ASSISTANT,
    COHORT_MANAGER,
    PERMISSIONS,
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
    """plan §2.3 권한표: 매니저는 조교 권한 + 계약·멘토·설정·배정·정산,
    팀리드는 매니저 + 담당자 배정(A36), SUPER_ADMIN은 전부."""
    admin = ROLES_BY_CODE[SUPER_ADMIN].permissions
    manager = ROLES_BY_CODE[COHORT_MANAGER].permissions
    team_lead = ROLES_BY_CODE[TEAM_LEAD].permissions
    assistant = ROLES_BY_CODE[COHORT_ASSISTANT].permissions
    assert admin == set(PERMISSIONS)
    assert assistant < manager < team_lead < admin
    assert team_lead - manager == {"staff.assign"}
    assert admin - team_lead == {"org.manage", "role.assign"}
    assert manager - assistant == {
        "contract.manage",
        "mentor.manage",
        "mentoring.settings.manage",
        "mentoring.assignment.manage",
        "mentoring.settlement.close",
    }
    assert {"org.manage", "role.assign"}.isdisjoint(manager)
    for role in ROLES_BY_CODE.values():
        assert role.permissions <= set(PERMISSIONS)


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
        ("UNKNOWN", RoleScopeType.GLOBAL, False, False),
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

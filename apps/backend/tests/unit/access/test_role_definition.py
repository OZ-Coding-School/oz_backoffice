"""역할 정의 규칙 (decisions A84)."""

import pytest

from app.contexts.access.domain.catalog import (
    COHORT_MANAGER,
    MENTOR,
    PERMISSIONS,
    SUPER_ADMIN,
    TEAM_LEAD,
)
from app.contexts.access.domain.enums import RoleScopeKind, RoleScopeType
from app.contexts.access.domain.roles import Role, builtin_scope_kind
from app.shared.errors import BusinessRuleViolation

pytestmark = pytest.mark.unit


def custom(kind: RoleScopeKind = RoleScopeKind.SCOPED) -> Role:
    return Role.create(code="AUDITOR", name=" 감사 담당 ", description="  ", scope_kind=kind)


def builtin(code: str) -> Role:
    return Role(code=code, name=code, description=None, scope_kind=builtin_scope_kind(code))


@pytest.mark.parametrize(
    ("code", "valid"),
    [
        ("AB", True),
        ("A" * 50, True),
        ("ROLE_2", True),
        ("A", False),  # 2자 미만
        ("A" * 51, False),
        ("2ROLE", False),  # 대문자로 시작
        ("role", False),
        ("RO-LE", False),
    ],
)
def test_code_rule(code: str, valid: bool) -> None:
    def build() -> Role:
        return Role.create(
            code=code, name="이름", description=None, scope_kind=RoleScopeKind.GLOBAL
        )

    if valid:
        assert build().code == code
    else:
        with pytest.raises(BusinessRuleViolation) as error:
            build()
        assert error.value.code == "invalid_role_code"


def test_name_and_description_are_trimmed_and_limited() -> None:
    role = custom()
    assert (role.name, role.description) == ("감사 담당", None)
    assert not role.is_builtin
    assert role.scopes == {RoleScopeType.BOOTCAMP, RoleScopeType.COHORT}

    role.rename(name="가" * 50, description="나" * 200)
    with pytest.raises(BusinessRuleViolation) as name_error:
        role.rename(name=" ", description=None)
    assert name_error.value.code == "invalid_role_name"
    with pytest.raises(BusinessRuleViolation) as long_name:
        role.rename(name="가" * 51, description=None)
    assert long_name.value.code == "invalid_role_name"
    with pytest.raises(BusinessRuleViolation) as long_description:
        role.rename(name="이름", description="나" * 201)
    assert long_description.value.code == "invalid_role_description"


def test_scoped_role_cannot_take_global_only_permissions() -> None:
    role = custom(RoleScopeKind.SCOPED)
    role.replace_permissions(["member.approval.read", "mentoring.request.read"])
    assert role.permissions == {"member.approval.read", "mentoring.request.read"}

    with pytest.raises(BusinessRuleViolation) as error:
        role.replace_permissions(["member.approval.read", "staff.assignment.read"])
    assert error.value.code == "global_only_permission"
    assert role.permissions == {"member.approval.read", "mentoring.request.read"}  # 그대로

    manager = builtin(COHORT_MANAGER)
    with pytest.raises(BusinessRuleViolation):
        manager.replace_permissions(["org.department.read"])

    global_role = custom(RoleScopeKind.GLOBAL)
    global_role.replace_permissions(
        ["org.department.read", "org.department.manage", "access.role.read"]
    )
    assert global_role.scopes == {RoleScopeType.GLOBAL}


def test_unknown_permission_is_rejected() -> None:
    with pytest.raises(BusinessRuleViolation) as error:
        custom().replace_permissions(["nope"])
    assert error.value.code == "permission_not_found"


@pytest.mark.parametrize("code", [SUPER_ADMIN, MENTOR])
def test_locked_roles(code: str) -> None:
    role = builtin(code)
    assert role.is_builtin
    assert role.permissions_locked
    with pytest.raises(BusinessRuleViolation) as error:
        role.replace_permissions([])
    assert error.value.code == "role_permissions_locked"


def test_super_admin_always_has_every_permission() -> None:
    assert builtin(SUPER_ADMIN).effective_permissions == set(PERMISSIONS)
    team_lead = builtin(TEAM_LEAD)
    assert team_lead.scope_kind is RoleScopeKind.GLOBAL
    assert not team_lead.permissions_locked
    team_lead.replace_permissions(["org.department.read"])
    assert team_lead.effective_permissions == {"org.department.read"}


@pytest.mark.parametrize(
    "codes",
    [
        ["org.department.manage"],
        ["academy.roster.sync"],
        ["mentoring.request.cancel"],
        ["mentoring.settlement.close"],
    ],
)
def test_manage_and_actions_need_read(codes: list[str]) -> None:
    """관리·동기화·취소·마감은 조회를 포함한다 (A86)."""
    role = custom(RoleScopeKind.GLOBAL)
    with pytest.raises(BusinessRuleViolation) as error:
        role.replace_permissions(codes)
    assert error.value.code == "permission_requires_read"

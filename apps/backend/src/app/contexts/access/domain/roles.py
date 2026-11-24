"""역할 정의 (decisions A84): 이름·설명·허용 범위·권한 묶음.

기본 역할(catalog.py)은 지울 수 없고, 최고 관리자는 항상 모든 권한이라 권한을 편집할 수 없다.
멘토·수강생은 소유 관계로 검사하므로 권한을 편집할 수 없다.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.contexts.access.domain.catalog import (
    BUILTIN_ROLE_CODES,
    GLOBAL_ONLY_PERMISSIONS,
    HIDDEN_ROLE_CODES,
    PERMISSIONS,
    ROLES_BY_CODE,
    SUPER_ADMIN,
    TEAM_LEAD,
)
from app.contexts.access.domain.enums import RoleScopeKind, RoleScopeType
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,49}$")
NAME_MAX_LENGTH = 50
DESCRIPTION_MAX_LENGTH = 200

SCOPES_OF_KIND: dict[RoleScopeKind, frozenset[RoleScopeType]] = {
    RoleScopeKind.GLOBAL: frozenset({RoleScopeType.GLOBAL}),
    RoleScopeKind.SCOPED: frozenset({RoleScopeType.BOOTCAMP, RoleScopeType.COHORT}),
}


def builtin_scope_kind(code: str) -> RoleScopeKind:
    scopes = ROLES_BY_CODE[code].scopes
    return RoleScopeKind.GLOBAL if RoleScopeType.GLOBAL in scopes else RoleScopeKind.SCOPED


def _clean_name(name: str) -> str:
    name = name.strip()
    if not 1 <= len(name) <= NAME_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"역할 이름은 1~{NAME_MAX_LENGTH}자로 적어 주세요.", code="invalid_role_name"
        )
    return name


def _clean_description(description: str | None) -> str | None:
    description = (description or "").strip() or None
    if description is not None and len(description) > DESCRIPTION_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"설명은 {DESCRIPTION_MAX_LENGTH}자까지 적을 수 있습니다.",
            code="invalid_role_description",
        )
    return description


@dataclass(kw_only=True, eq=False)
class Role(AggregateRoot):
    code: str
    name: str
    description: str | None
    scope_kind: RoleScopeKind
    permissions: frozenset[str] = frozenset()

    @classmethod
    def create(
        cls, *, code: str, name: str, description: str | None, scope_kind: RoleScopeKind
    ) -> "Role":
        if not CODE_PATTERN.match(code):
            raise BusinessRuleViolation(
                "역할 코드는 영문 대문자로 시작하는 대문자·숫자·밑줄 2~50자로 적어 주세요.",
                code="invalid_role_code",
            )
        return cls(
            code=code,
            name=_clean_name(name),
            description=_clean_description(description),
            scope_kind=scope_kind,
        )

    @property
    def is_builtin(self) -> bool:
        return self.code in BUILTIN_ROLE_CODES

    @property
    def is_hidden(self) -> bool:
        return self.code in HIDDEN_ROLE_CODES

    @property
    def permissions_locked(self) -> bool:
        return self.code == SUPER_ADMIN or self.is_hidden

    @property
    def scopes(self) -> frozenset[RoleScopeType]:
        if self.is_builtin:
            return ROLES_BY_CODE[self.code].scopes
        return SCOPES_OF_KIND[self.scope_kind]

    @property
    def effective_permissions(self) -> frozenset[str]:
        """판정에 쓰는 권한. 최고 관리자는 항상 모든 권한이다."""
        return frozenset(PERMISSIONS) if self.code == SUPER_ADMIN else self.permissions

    def rename(self, *, name: str, description: str | None) -> None:
        self.name = _clean_name(name)
        self.description = _clean_description(description)

    def replace_permissions(self, codes: Iterable[str]) -> None:
        if self.permissions_locked:
            raise BusinessRuleViolation(
                "이 역할의 권한은 바꿀 수 없습니다.", code="role_permissions_locked"
            )
        wanted = frozenset(codes)
        unknown = sorted(wanted - PERMISSIONS.keys())
        if unknown:
            raise BusinessRuleViolation(
                f"정의되지 않은 권한입니다: {', '.join(unknown)}", code="permission_not_found"
            )
        if self.scope_kind is not RoleScopeKind.GLOBAL:
            global_only = sorted(wanted & GLOBAL_ONLY_PERMISSIONS)
            if global_only:
                raise BusinessRuleViolation(
                    "과정·기수 범위 역할에는 전체 범위 전용 권한을 줄 수 없습니다: "
                    + ", ".join(global_only),
                    code="global_only_permission",
                )
        self.permissions = wanted


def is_directly_managed(code: str) -> bool:
    """역할 화면에서 직접 부여·회수하는 역할: 최고 관리자·팀리드·새 역할 (A17·A36·A85).

    운영 매니저·조교는 담당자 배정, 멘토·수강생은 배정·가입에서만 바뀐다.
    """
    return code in (SUPER_ADMIN, TEAM_LEAD) or code not in BUILTIN_ROLE_CODES

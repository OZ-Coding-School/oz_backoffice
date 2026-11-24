from enum import StrEnum


class RoleScopeType(StrEnum):
    GLOBAL = "GLOBAL"
    BOOTCAMP = "BOOTCAMP"
    COHORT = "COHORT"


class RoleScopeKind(StrEnum):
    """역할을 줄 수 있는 범위 (A84). GLOBAL = 전체, SCOPED = 과정·기수."""

    GLOBAL = "GLOBAL"
    SCOPED = "SCOPED"

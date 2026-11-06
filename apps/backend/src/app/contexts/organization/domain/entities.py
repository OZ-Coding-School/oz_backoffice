"""organization 도메인 엔티티: 부서, 직위, 직원, 과정·기수 담당자.

부서는 조직도 용도이며 데이터 소유 범위가 아니다 (decisions D5).
조교·운영매니저는 내부 직원이다 (D8). 담당자 배정은 표시용이고 권한은 user_roles와 동기화한다 (D4).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.organization.domain.enums import EmploymentType, StaffRole
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(kw_only=True, eq=False)
class Department(AggregateRoot):
    """부서. 같은 상위 부서 안에서 이름은 유일하다 (최상위끼리도 유일)."""

    name: str
    description: str
    parent_id: uuid.UUID | None = None
    rules: str | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.description = self.description.strip()
        _require(0 < len(self.name) <= 20, "부서명은 1~20자여야 합니다.", "invalid_department")
        _require(
            0 < len(self.description) <= 500,
            "부서 설명은 1~500자여야 합니다.",
            "invalid_department",
        )
        _require(
            self.parent_id != self.id,
            "자기 자신을 상위 부서로 지정할 수 없습니다.",
            "invalid_department",
        )

    def move_under(self, parent_id: uuid.UUID | None) -> None:
        """상위 부서를 바꾼다. 여러 단계에 걸친 순환은 부서 트리를 조회하는 서비스에서 검사한다."""
        _require(
            parent_id != self.id,
            "자기 자신을 상위 부서로 지정할 수 없습니다.",
            "invalid_department",
        )
        self.parent_id = parent_id


@dataclass(kw_only=True, eq=False)
class EmployeePosition(AggregateRoot):
    """직위. priority가 작을수록 높은 직급이다."""

    name: str
    priority: int

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        _require(0 < len(self.name) <= 20, "직위명은 1~20자여야 합니다.", "invalid_position")
        _require(self.priority >= 0, "직급 우선순위는 0 이상이어야 합니다.", "invalid_position")


@dataclass(kw_only=True, eq=False)
class Employee(AggregateRoot):
    """사내 직원. 회원 1명당 직원 정보는 하나다."""

    user_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType

    def transfer(self, *, department_id: uuid.UUID, position_id: uuid.UUID) -> None:
        self.department_id = department_id
        self.position_id = position_id

    def change_employment_type(self, employment_type: EmploymentType) -> None:
        self.employment_type = employment_type


@dataclass(kw_only=True, eq=False)
class BootcampStaff(AggregateRoot):
    """과정 담당자. (직원, 과정, 역할)은 유일하다."""

    employee_id: uuid.UUID
    bootcamp_id: uuid.UUID
    role: StaffRole
    created_at: datetime | None = None


@dataclass(kw_only=True, eq=False)
class CohortStaff(AggregateRoot):
    """기수 담당자 (운영 매니저 / 조교). (직원, 기수, 역할)은 유일하다."""

    employee_id: uuid.UUID
    cohort_id: uuid.UUID
    role: StaffRole
    created_at: datetime | None = None

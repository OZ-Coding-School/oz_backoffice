"""organization 도메인 엔티티: 부서, 팀, 직위, 직원, 과정·기수 담당자.

부서는 조직도 용도이며 데이터 소유 범위가 아니다 (decisions D5).
부서 아래에 팀이 있고, 과정은 담당 팀 하나에 소속된다 (A62).
조교·운영매니저는 내부 직원이다 (D8). 담당자 배정은 표시용이고 권한은 user_roles와 동기화한다 (D4).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.organization.domain.enums import (
    AssignmentScope,
    DataScope,
    EmploymentType,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(kw_only=True, eq=False)
class Department(AggregateRoot):
    """부서. 이름은 유일하다. 하위 조직은 팀(`Team`)으로 둔다 (A62)."""

    name: str
    description: str
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

    def update(self, *, name: str, description: str, rules: str | None) -> None:
        """이름·설명·규칙을 바꾼다. 검증은 생성할 때와 같다."""
        changed = Department(id=self.id, name=name, description=description, rules=rules)
        self.name, self.description, self.rules = changed.name, changed.description, changed.rules


@dataclass(kw_only=True, eq=False)
class Team(AggregateRoot):
    """팀. 한 부서에 소속되고 같은 부서 안에서 이름은 유일하다 (A62)."""

    department_id: uuid.UUID
    name: str
    description: str | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if self.description is not None:
            self.description = self.description.strip() or None
        _require(0 < len(self.name) <= 20, "팀 이름은 1~20자여야 합니다.", "invalid_team")
        _require(
            self.description is None or len(self.description) <= 500,
            "팀 설명은 500자 이내여야 합니다.",
            "invalid_team",
        )

    def update(self, *, department_id: uuid.UUID, name: str, description: str | None) -> None:
        changed = Team(id=self.id, department_id=department_id, name=name, description=description)
        self.department_id, self.name, self.description = (
            changed.department_id,
            changed.name,
            changed.description,
        )


@dataclass(frozen=True, slots=True)
class BootcampTeam:
    """과정의 담당 팀 (과정당 한 팀, A62)."""

    bootcamp_id: uuid.UUID
    team_id: uuid.UUID


@dataclass(kw_only=True, eq=False)
class EmployeePosition(AggregateRoot):
    """직위. priority가 작을수록 높은 직급이다.

    assignment_scope는 운영진 정보 입력에서 담당을 고르는 방식이다 (A62).
    직위가 곧 역할이다(A87): 권한 묶음은 따로 저장하고, data_scope가 기수 데이터의 범위를 정한다.
    """

    name: str
    priority: int
    assignment_scope: AssignmentScope | None = None
    data_scope: DataScope = DataScope.ASSIGNED

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        _require(0 < len(self.name) <= 20, "직위명은 1~20자여야 합니다.", "invalid_position")
        _require(self.priority >= 0, "직급 우선순위는 0 이상이어야 합니다.", "invalid_position")

    def update(
        self,
        *,
        name: str,
        priority: int,
        assignment_scope: AssignmentScope | None,
        data_scope: DataScope | None = None,
    ) -> None:
        changed = EmployeePosition(
            id=self.id,
            name=name,
            priority=priority,
            assignment_scope=assignment_scope,
            data_scope=data_scope or self.data_scope,
        )
        self.name, self.priority = changed.name, changed.priority
        self.assignment_scope = changed.assignment_scope
        self.data_scope = changed.data_scope


@dataclass(kw_only=True, eq=False)
class Employee(AggregateRoot):
    """사내 직원. 회원 1명당 직원 정보는 하나다."""

    user_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType
    team_id: uuid.UUID | None = None  # 팀 없이 부서 직속일 수 있다 (A62)

    def transfer(
        self, *, department_id: uuid.UUID, team_id: uuid.UUID | None, position_id: uuid.UUID
    ) -> None:
        self.department_id = department_id
        self.team_id = team_id
        self.position_id = position_id

    def change_employment_type(self, employment_type: EmploymentType) -> None:
        self.employment_type = employment_type


@dataclass(kw_only=True, eq=False)
class BootcampStaff(AggregateRoot):
    """과정 담당자. (직원, 과정, 역할)은 유일하다."""

    employee_id: uuid.UUID
    bootcamp_id: uuid.UUID
    created_at: datetime | None = None


@dataclass(kw_only=True, eq=False)
class CohortStaff(AggregateRoot):
    """기수 담당자 (운영 매니저 / 조교). (직원, 기수, 역할)은 유일하다."""

    employee_id: uuid.UUID
    cohort_id: uuid.UUID
    created_at: datetime | None = None

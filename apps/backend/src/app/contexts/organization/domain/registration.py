"""운영진 가입 신청 (decisions A11).

최초 로그인한 운영진이 부서·직위·고용 형태·담당(역할 + 과정 또는 기수)을 입력해 신청한다.
어드민이 항목을 조정해 승인하면 직원·담당자가 만들어진다 (승인·반려는 P3).
담당 역할과 과정·기수는 직위와 연결하지 않고 신청자가 직접 고른다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

MAX_ASSIGNMENTS = 20


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(frozen=True, slots=True)
class RequestedAssignment:
    """신청한 담당 1건: 역할 + 과정 또는 기수 (둘 중 하나만)."""

    role: StaffRole
    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        _require(
            (self.bootcamp_id is None) != (self.cohort_id is None),
            "담당은 과정 또는 기수 중 하나만 지정해야 합니다.",
            "invalid_staff_assignment",
        )


def _validate_assignments(assignments: list[RequestedAssignment]) -> None:
    _require(
        len(assignments) <= MAX_ASSIGNMENTS,
        f"담당은 {MAX_ASSIGNMENTS}개까지 신청할 수 있습니다.",
        "invalid_staff_assignment",
    )
    _require(
        len(set(assignments)) == len(assignments),
        "같은 담당을 두 번 신청할 수 없습니다.",
        "duplicate_staff_assignment",
    )


@dataclass(kw_only=True, eq=False)
class EmployeeRegistration(AggregateRoot):
    """운영진 가입 신청. 회원당 대기(PENDING) 신청은 하나다."""

    user_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[RequestedAssignment] = field(default_factory=list)
    status: EmployeeRegistrationStatus = EmployeeRegistrationStatus.PENDING
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        _validate_assignments(self.assignments)
        _require(
            (self.status is EmployeeRegistrationStatus.PENDING) == (self.reviewed_at is None),
            "신청 상태와 검토 시각이 맞지 않습니다.",
            "invalid_registration",
        )

    @property
    def is_pending(self) -> bool:
        return self.status is EmployeeRegistrationStatus.PENDING

    def update(
        self,
        *,
        department_id: uuid.UUID,
        position_id: uuid.UUID,
        employment_type: EmploymentType,
        assignments: list[RequestedAssignment],
    ) -> None:
        """대기 중인 신청만 신청자가 고칠 수 있다."""
        _require(
            self.is_pending, "검토가 끝난 신청은 고칠 수 없습니다.", "registration_not_pending"
        )
        _validate_assignments(assignments)
        self.department_id = department_id
        self.position_id = position_id
        self.employment_type = employment_type
        self.assignments = list(assignments)

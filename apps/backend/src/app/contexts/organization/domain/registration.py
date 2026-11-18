"""운영진 가입 신청 (decisions A11).

최초 로그인한 운영진이 부서·팀·직위·고용 형태·담당(역할 + 과정 또는 기수)을 입력해 신청한다.
어드민이 항목을 조정해 승인하면 직원·담당자가 만들어진다 (승인·반려는 P3-2b).
담당은 소속 팀의 과정 안에서 직위의 담당 방식대로 고른다 (A62, `check_assignment_scope`).
신청할 때만 이 규칙을 검사하고 승인할 때 어드민의 조정은 자유다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.contexts.organization.domain.enums import (
    AssignmentScope,
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

MAX_ASSIGNMENTS = 20
REJECT_REASON_MAX_LENGTH = 300


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


def check_assignment_scope(
    scope: AssignmentScope | None,
    assignments: list[RequestedAssignment],
    *,
    team_bootcamp_ids: set[uuid.UUID],
    cohort_bootcamps: dict[uuid.UUID, uuid.UUID],
) -> None:
    """직위 담당 방식에 맞는 담당인지 검사한다 (A62, 신청할 때만).

    - 담당 방식 없음: 담당을 고를 수 없다
    - COURSE: 운영 매니저 + 소속 팀의 과정 (여러 개)
    - COHORT: 조교 + 소속 팀 과정의 기수 (하나)
    `cohort_bootcamps`는 기수 → 과정. 팀이 없으면 `team_bootcamp_ids`가 비어 담당을 고를 수 없다.
    """
    if not assignments:
        return
    if scope is None:
        raise BusinessRuleViolation(
            "이 직위는 담당 과정·기수를 고르지 않습니다.", code="invalid_staff_assignment"
        )
    if scope is AssignmentScope.COHORT:
        _require(
            len(assignments) <= 1,
            "조교 직위는 기수를 하나만 고를 수 있습니다.",
            "invalid_staff_assignment",
        )
    for a in assignments:
        if scope is AssignmentScope.COURSE:
            ok = (
                a.role is StaffRole.MANAGER
                and a.bootcamp_id is not None
                and a.bootcamp_id in team_bootcamp_ids
            )
            message = "소속 팀이 담당하는 과정을 운영 매니저로 골라야 합니다."
        else:
            ok = (
                a.role is StaffRole.ASSISTANT
                and a.cohort_id is not None
                and cohort_bootcamps.get(a.cohort_id) in team_bootcamp_ids
            )
            message = "소속 팀 과정의 기수를 조교로 골라야 합니다."
        _require(ok, message, "invalid_staff_assignment")


@dataclass(kw_only=True, eq=False)
class EmployeeRegistration(AggregateRoot):
    """운영진 가입 신청. 회원당 대기(PENDING) 신청은 하나다."""

    user_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType
    team_id: uuid.UUID | None = None  # 팀 없이 부서 직속일 수 있다 (A62)
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
        team_id: uuid.UUID | None,
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
        self.team_id = team_id
        self.position_id = position_id
        self.employment_type = employment_type
        self.assignments = list(assignments)

    def approve(
        self,
        *,
        now: datetime,
        department_id: uuid.UUID,
        team_id: uuid.UUID | None,
        position_id: uuid.UUID,
        employment_type: EmploymentType,
        assignments: list[RequestedAssignment],
    ) -> None:
        """어드민이 (조정한) 항목으로 승인한다. 승인된 항목이 직원·담당자의 원천이 된다."""
        _require(self.is_pending, "이미 검토가 끝난 신청입니다.", "registration_not_pending")
        _validate_assignments(assignments)
        self.department_id = department_id
        self.team_id = team_id
        self.position_id = position_id
        self.employment_type = employment_type
        self.assignments = list(assignments)
        self.status = EmployeeRegistrationStatus.APPROVED
        self.reviewed_at = now

    def reject(self, *, now: datetime, reason: str) -> None:
        _require(self.is_pending, "이미 검토가 끝난 신청입니다.", "registration_not_pending")
        reason = reason.strip()
        _require(
            0 < len(reason) <= REJECT_REASON_MAX_LENGTH,
            f"반려 사유는 1~{REJECT_REASON_MAX_LENGTH}자여야 합니다.",
            "invalid_reject_reason",
        )
        self.status = EmployeeRegistrationStatus.REJECTED
        self.reviewed_at = now
        self.reject_reason = reason

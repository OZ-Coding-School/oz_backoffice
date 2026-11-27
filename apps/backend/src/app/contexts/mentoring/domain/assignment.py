"""기수에 멘토를 배정한 내용 (decisions A35·A110, M13·M30).

- 배정은 **근거 계약**(`contract_id`, 그 멘토의 멘토 계약)을 가리키고, 정산 조건(단가·단가 기준·노쇼
  금액·정산 시간 기준)은 근거 계약에서 읽는다(A110). 배정에는 기간·활성만 남는다.
- 활성 배정은 (멘토, 기수)당 하나(DB 부분 유니크, 유형 구분 없음 A41).
- 시작일은 기수 기간 안이어야 하고, 종료일은 없어도 되며 기수 기간 밖이어도 된다.
- 배정 기간은 근거 계약 기간 안이어야 한다(검사는 서비스, 계약은 educator).
- 종료일이 지나면(다음 날 00:00 KST) 비활성화한다. 삭제는 비활성화다.
- 비활성 배정은 종료일이 없거나 오늘 이후일 때 다시 활성화한다(멘토 활성·중복·계약 검사는 서비스).
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

EDITABLE_FIELDS = frozenset({"start_date", "end_date", "contract_id"})


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(frozen=True, slots=True)
class AssignmentTerms:
    """근거 계약에서 읽은 멘토링 정산 조건 (A110)."""

    settlement_policy: MentoringSettlementPolicy
    pay_unit: PayUnit  # HOURLY·PER_SESSION만
    pay_rate: int
    no_show_pay_amount: int


@dataclass(kw_only=True, eq=False)
class CohortMentor(AggregateRoot):
    cohort_id: uuid.UUID
    mentor_id: uuid.UUID
    contract_id: uuid.UUID
    start_date: date
    end_date: date | None = None
    is_active: bool = True
    deactivated_at: datetime | None = None
    deactivation_reason: CohortMentorDeactivationReason | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _rule(
            self.end_date is None or self.start_date <= self.end_date,
            "멘토링 시작일이 종료일보다 늦습니다.",
            "invalid_assignment_period",
        )

    def ensure_starts_within(self, cohort_start: date, cohort_end: date) -> None:
        _rule(
            cohort_start <= self.start_date <= cohort_end,
            "멘토링 시작일은 기수 기간 안이어야 합니다.",
            "assignment_start_outside_cohort",
        )

    def ensure_within_contract(
        self, contract_start: date | None, contract_end: date | None
    ) -> None:
        """배정 기간이 근거 계약 기간 안인지 (A110). 배정 종료일이 없으면 계약이 끝날 때까지다."""
        after_start = contract_start is None or contract_start <= self.start_date
        before_end = contract_end is None or (
            self.start_date <= contract_end
            and (self.end_date is None or self.end_date <= contract_end)
        )
        inside = after_start and before_end
        _rule(
            inside,
            "멘토링 기간이 근거 계약 기간 밖입니다.",
            "assignment_outside_contract_period",
        )

    def trimmed_to(self, contract_start: date | None, contract_end: date | None) -> bool:
        """계약 기간이 줄었을 때 배정 기간을 계약 기간으로 줄인다 (A110).

        줄였거나 그대로면 True, 남는 기간이 없으면 False(호출한 쪽이 비활성화한다)."""
        start = self.start_date
        end = self.end_date
        if contract_start is not None and start < contract_start:
            start = contract_start
        if contract_end is not None and (end is None or end > contract_end):
            end = contract_end
        if end is not None and start > end:
            return False
        self.start_date = start
        self.end_date = end
        return True

    def revised(self, values: dict[str, Any]) -> "CohortMentor":
        _rule(
            set(values) <= EDITABLE_FIELDS, "바꿀 수 없는 항목입니다.", "invalid_assignment_field"
        )
        return dataclasses.replace(self, **values)

    def deactivate(self, reason: CohortMentorDeactivationReason, *, now: datetime) -> None:
        _rule(self.is_active, "이미 비활성화된 배정입니다.", "assignment_already_inactive")
        self.is_active = False
        self.deactivated_at = now
        self.deactivation_reason = reason

    def reactivate(self, *, today: date) -> None:
        _rule(not self.is_active, "이미 활성화된 배정입니다.", "assignment_already_active")
        _rule(
            self.end_date is None or self.end_date >= today,
            "종료일이 지난 배정입니다. 종료일을 먼저 바꾸세요.",
            "assignment_period_ended",
        )
        self.is_active = True
        self.deactivated_at = None
        self.deactivation_reason = None

    def is_expired(self, today: date) -> bool:
        return self.is_active and self.end_date is not None and self.end_date < today

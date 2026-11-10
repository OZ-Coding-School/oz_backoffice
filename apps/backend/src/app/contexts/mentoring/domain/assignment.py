"""기수에 멘토를 배정한 내용 (decisions A35, M13·M30).

- 계약과 별개로 운영진이 관리한다. 활성 배정은 (멘토, 기수, 유형)당 하나(DB 부분 유니크).
- 시작일은 기수 기간 안이어야 하고, 종료일은 없어도 되며 기수 기간 밖이어도 된다.
- 종료일이 지나면(다음 날 00:00 KST) 비활성화한다. 삭제는 비활성화다.
- 기간·정산 조건은 언제든 바꾼다(멘토·기수·유형은 바꾸지 않는다).
- 비활성 배정은 종료일이 없거나 오늘 이후일 때 다시 활성화한다(멘토 활성·중복 검사는 서비스).
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringPeriodType,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

ASSIGNMENT_PAY_UNITS = (PayUnit.HOURLY, PayUnit.PER_SESSION)
EDITABLE_FIELDS = frozenset(
    {
        "start_date",
        "end_date",
        "cost_settlement_policy",
        "pay_unit",
        "pay_rate",
        "no_show_pay_amount",
    }
)


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(kw_only=True, eq=False)
class CohortMentor(AggregateRoot):
    cohort_id: uuid.UUID
    mentor_id: uuid.UUID
    period_type: MentoringPeriodType
    start_date: date
    cost_settlement_policy: MentoringSettlementPolicy
    pay_unit: PayUnit
    pay_rate: int
    end_date: date | None = None
    no_show_pay_amount: int = 0
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
        _rule(
            self.pay_unit in ASSIGNMENT_PAY_UNITS,
            "단가 기준은 시급 또는 회당입니다.",
            "invalid_pay_unit",
        )
        _rule(
            self.pay_rate >= 0 and self.no_show_pay_amount >= 0,
            "단가와 노쇼 금액은 0원 이상이어야 합니다.",
            "invalid_pay_amount",
        )

    def ensure_starts_within(self, cohort_start: date, cohort_end: date) -> None:
        _rule(
            cohort_start <= self.start_date <= cohort_end,
            "멘토링 시작일은 기수 기간 안이어야 합니다.",
            "assignment_start_outside_cohort",
        )

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

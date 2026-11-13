"""멘토링 정산 (decisions M16·M29·M30·A55).

- 단위: 멘토 × 월(KST) × 기수. DRAFT에서 집계하고 CLOSED로 마감한다. 마감하면 바꿀 수 없다.
- 명세(세션 단위)에 정산 시점 단가·정산 기준을 스냅샷한다. 세션은 한 번만 정산된다(DB 유니크).
- 정산 시간: 배정의 정산 기준이 실제 진행이면 기록한 진행 시간, 신청 시간이면 신청 시간.
- 금액: 시급 = floor(단가 × 분 / 60), 회당 = 단가 (원 미만 내림, M30). 노쇼 = 배정의 노쇼 고정 금액.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def billable_minutes(
    policy: MentoringSettlementPolicy, *, requested: int, recorded: int | None
) -> int:
    if policy is MentoringSettlementPolicy.STUDENT_REQUEST:
        return requested
    return recorded or 0


def session_amount(pay_unit: PayUnit, pay_rate: int, minutes: int) -> int:
    _rule(
        pay_unit in (PayUnit.HOURLY, PayUnit.PER_SESSION),
        "멘토링 정산은 시급·회당 단가만 씁니다.",
        "invalid_pay_unit",
    )
    if pay_unit is PayUnit.PER_SESSION:
        return pay_rate
    return pay_rate * minutes // 60  # 원 미만 내림


def month_start(value: date) -> date:
    return value.replace(day=1)


def next_month(value: date) -> date:
    first = month_start(value)
    return (
        first.replace(year=first.year + 1, month=1)
        if first.month == 12
        else first.replace(month=first.month + 1)
    )


@dataclass(kw_only=True, eq=False)
class SettlementItem(Entity):
    session_id: uuid.UUID
    cohort_id: uuid.UUID
    item_type: SettlementItemType
    settlement_policy: MentoringSettlementPolicy
    billable_minutes: int
    pay_unit: PayUnit
    pay_rate: int
    amount: int
    session_starts_at: datetime | None = None  # 조회용 (저장하지 않음)
    created_at: datetime | None = None


@dataclass(kw_only=True, eq=False)
class MentoringSettlement(AggregateRoot):
    mentor_id: uuid.UUID
    cohort_id: uuid.UUID
    settlement_month: date
    status: MentoringSettlementStatus = MentoringSettlementStatus.DRAFT
    items: list[SettlementItem] = field(default_factory=list)
    closed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.settlement_month = month_start(self.settlement_month)

    @property
    def session_count(self) -> int:
        return len(self.items)

    @property
    def total_minutes(self) -> int:
        return sum(i.billable_minutes for i in self.items)

    @property
    def total_amount(self) -> int:
        return sum(i.amount for i in self.items)

    @property
    def is_closed(self) -> bool:
        return self.status is MentoringSettlementStatus.CLOSED

    def replace_items(self, items: list[SettlementItem]) -> None:
        """다시 집계: DRAFT만 새로 계산한다."""
        _rule(not self.is_closed, "마감한 정산은 바꿀 수 없습니다.", "settlement_closed")
        self.items = list(items)

    def close(self, now: datetime) -> None:
        _rule(not self.is_closed, "이미 마감한 정산입니다.", "settlement_closed")
        self.status = MentoringSettlementStatus.CLOSED
        self.closed_at = now

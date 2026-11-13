"""정산 계산·상태 (M16·M29·M30·A55)."""

from datetime import UTC, date, datetime

import pytest

from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.contexts.mentoring.domain.settlement import (
    MentoringSettlement,
    SettlementItem,
    billable_minutes,
    next_month,
    session_amount,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def test_billable_minutes_by_policy() -> None:
    actual = MentoringSettlementPolicy.ACTUAL_DURATION
    request = MentoringSettlementPolicy.STUDENT_REQUEST
    assert billable_minutes(actual, requested=60, recorded=90) == 90
    assert billable_minutes(request, requested=60, recorded=90) == 60
    assert billable_minutes(actual, requested=60, recorded=None) == 0


def test_amount_floors_and_units() -> None:
    assert session_amount(PayUnit.HOURLY, 30000, 90) == 45000
    assert session_amount(PayUnit.HOURLY, 33333, 30) == 16666  # 16666.5 → 내림
    assert session_amount(PayUnit.HOURLY, 10001, 1) == 166  # 166.68 → 내림
    assert session_amount(PayUnit.PER_SESSION, 50000, 30) == 50000
    with pytest.raises(BusinessRuleViolation):
        session_amount(PayUnit.MONTHLY, 1, 1)


def test_months() -> None:
    assert next_month(date(2026, 12, 15)) == date(2027, 1, 1)
    assert next_month(date(2026, 11, 1)) == date(2026, 12, 1)


def test_settlement_totals_and_close() -> None:
    settlement = MentoringSettlement(
        mentor_id=new_id(), cohort_id=new_id(), settlement_month=date(2026, 11, 20)
    )
    assert settlement.settlement_month == date(2026, 11, 1)

    def item(amount: int, minutes: int, kind: SettlementItemType) -> SettlementItem:
        return SettlementItem(
            session_id=new_id(),
            cohort_id=settlement.cohort_id,
            item_type=kind,
            settlement_policy=MentoringSettlementPolicy.ACTUAL_DURATION,
            billable_minutes=minutes,
            pay_unit=PayUnit.HOURLY,
            pay_rate=30000,
            amount=amount,
        )

    settlement.replace_items(
        [item(30000, 60, SettlementItemType.SESSION), item(10000, 0, SettlementItemType.NO_SHOW)]
    )
    assert (settlement.session_count, settlement.total_minutes, settlement.total_amount) == (
        2,
        60,
        40000,
    )
    now = datetime(2026, 12, 3, tzinfo=UTC)
    settlement.close(now)
    assert (settlement.status, settlement.closed_at) == (MentoringSettlementStatus.CLOSED, now)
    with pytest.raises(BusinessRuleViolation) as closed:
        settlement.replace_items([])
    assert closed.value.code == "settlement_closed"
    with pytest.raises(BusinessRuleViolation):
        settlement.close(now)

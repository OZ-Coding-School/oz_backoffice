from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 10, tzinfo=UTC)
TODAY = date(2026, 11, 10)


def assignment(**overrides: Any) -> CohortMentor:
    values: dict[str, Any] = {
        "cohort_id": new_id(),
        "mentor_id": new_id(),
        "start_date": date(2026, 11, 1),
        "end_date": date(2027, 4, 30),
        "cost_settlement_policy": MentoringSettlementPolicy.ACTUAL_DURATION,
        "pay_unit": PayUnit.HOURLY,
        "pay_rate": 30000,
    }
    values.update(overrides)
    return CohortMentor(**values)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"end_date": date(2026, 10, 1)}, "invalid_assignment_period"),
        ({"pay_unit": PayUnit.MONTHLY}, "invalid_pay_unit"),
        ({"pay_rate": -1}, "invalid_pay_amount"),
        ({"no_show_pay_amount": -1}, "invalid_pay_amount"),
    ],
)
def test_validation(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        assignment(**overrides)
    assert exc.value.code == code


def test_open_ended_and_start_within_cohort() -> None:
    open_ended = assignment(end_date=None)
    assert not open_ended.is_expired(date(2099, 1, 1))
    open_ended.ensure_starts_within(date(2026, 11, 1), date(2027, 4, 30))  # 시작일이 경계
    with pytest.raises(BusinessRuleViolation) as exc:
        assignment(start_date=date(2027, 5, 1), end_date=None).ensure_starts_within(
            date(2026, 11, 1), date(2027, 4, 30)
        )
    assert exc.value.code == "assignment_start_outside_cohort"


def test_revise_only_period_and_pay() -> None:
    current = assignment()
    revised = current.revised({"pay_rate": 40000, "end_date": None})
    assert (revised.id, revised.pay_rate, revised.end_date) == (current.id, 40000, None)
    with pytest.raises(BusinessRuleViolation) as exc:
        current.revised({"mentor_id": new_id()})
    assert exc.value.code == "invalid_assignment_field"


def test_deactivate_and_reactivate() -> None:
    a = assignment()
    a.deactivate(CohortMentorDeactivationReason.MANUAL, now=NOW)
    assert (a.is_active, a.deactivated_at, a.deactivation_reason) == (
        False,
        NOW,
        CohortMentorDeactivationReason.MANUAL,
    )
    with pytest.raises(BusinessRuleViolation):
        a.deactivate(CohortMentorDeactivationReason.MANUAL, now=NOW)
    a.reactivate(today=TODAY)
    assert (a.is_active, a.deactivated_at, a.deactivation_reason) == (True, None, None)

    ended = assignment(end_date=date(2026, 11, 9))
    ended.deactivate(CohortMentorDeactivationReason.EXPIRED, now=NOW)
    with pytest.raises(BusinessRuleViolation) as exc:
        ended.reactivate(today=TODAY)
    assert exc.value.code == "assignment_period_ended"


def test_expiry_boundary() -> None:
    a = assignment(end_date=TODAY)
    assert not a.is_expired(TODAY)  # 종료일 당일까지 활성
    assert a.is_expired(date(2026, 11, 11))

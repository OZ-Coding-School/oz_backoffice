from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import CohortMentorDeactivationReason
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
        "contract_id": new_id(),
    }
    values.update(overrides)
    return CohortMentor(**values)


def test_validation() -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        assignment(end_date=date(2026, 10, 1))
    assert exc.value.code == "invalid_assignment_period"


@pytest.mark.parametrize(
    ("start", "end", "contract", "inside"),
    [
        (date(2026, 11, 1), None, (None, None), True),
        (date(2026, 11, 1), None, (date(2026, 11, 1), date(2027, 1, 31)), True),
        (date(2026, 11, 1), date(2027, 1, 31), (date(2026, 11, 1), date(2027, 1, 31)), True),
        (date(2026, 10, 31), None, (date(2026, 11, 1), None), False),
        (date(2026, 11, 1), date(2027, 2, 1), (None, date(2027, 1, 31)), False),
        (date(2027, 2, 1), None, (None, date(2027, 1, 31)), False),
    ],
)
def test_within_contract(
    start: date, end: date | None, contract: tuple[date | None, date | None], inside: bool
) -> None:
    """배정 기간은 근거 계약 기간 안 (A110). 배정 종료일이 없으면 계약이 끝날 때까지다."""
    a = assignment(start_date=start, end_date=end)
    if inside:
        a.ensure_within_contract(*contract)
    else:
        with pytest.raises(BusinessRuleViolation) as exc:
            a.ensure_within_contract(*contract)
        assert exc.value.code == "assignment_outside_contract_period"


def test_trimmed_to_contract() -> None:
    a = assignment(start_date=date(2026, 11, 1), end_date=None)
    assert a.trimmed_to(date(2026, 11, 10), date(2026, 12, 31))
    assert (a.start_date, a.end_date) == (date(2026, 11, 10), date(2026, 12, 31))
    assert not assignment(start_date=date(2027, 1, 5), end_date=None).trimmed_to(
        None, date(2026, 12, 31)
    )


def test_open_ended_and_start_within_cohort() -> None:
    open_ended = assignment(end_date=None)
    assert not open_ended.is_expired(date(2099, 1, 1))
    open_ended.ensure_starts_within(date(2026, 11, 1), date(2027, 4, 30))  # 시작일이 경계
    with pytest.raises(BusinessRuleViolation) as exc:
        assignment(start_date=date(2027, 5, 1), end_date=None).ensure_starts_within(
            date(2026, 11, 1), date(2027, 4, 30)
        )
    assert exc.value.code == "assignment_start_outside_cohort"


def test_revise_only_period_and_contract() -> None:
    current = assignment()
    contract_id = new_id()
    revised = current.revised({"contract_id": contract_id, "end_date": None})
    assert (revised.id, revised.contract_id, revised.end_date) == (current.id, contract_id, None)
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

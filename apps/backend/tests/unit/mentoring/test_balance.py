"""멘토링 시간 계좌 규칙 (M9·A39·A40)."""

from datetime import date
from typing import Any

import pytest

from app.contexts.mentoring.domain.balance import BalanceAccount, ensure_validity
from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 11)
COHORT = {"cohort_start": date(2026, 11, 1), "cohort_end": date(2027, 4, 30)}


def _account(**overrides: Any) -> BalanceAccount:
    values: dict[str, Any] = {
        "student_id": new_id(),
        "valid_from": date(2026, 11, 1),
        "valid_until": date(2027, 4, 30),
    }
    values.update(overrides)
    return BalanceAccount(**values)


def test_owner_and_validity() -> None:
    with pytest.raises(BusinessRuleViolation):
        _account(team_id=new_id())  # 둘 다
    with pytest.raises(BusinessRuleViolation):
        _account(student_id=None)  # 둘 다 없음
    _account(student_id=None, team_id=new_id())
    with pytest.raises(BusinessRuleViolation):
        _account(valid_from=date(2027, 5, 1))


def test_grant_and_adjust() -> None:
    account = _account()
    entry = account.grant(120, " 기본 지급 ", today=TODAY)
    assert (entry.type, entry.amount, entry.after_remaining, entry.reason) == (
        MentoringBalanceTransactionType.STAFF_GRANT,
        120,
        120,
        "기본 지급",
    )
    down = account.adjust(-120, "오지급 정정", today=TODAY)  # 잔여와 정확히 같은 값
    assert (down.amount, account.remaining_minutes, account.total_minutes) == (-120, 0, 0)
    with pytest.raises(BusinessRuleViolation) as short:
        account.adjust(-60, "초과", today=TODAY)
    assert short.value.code == "insufficient_balance"


@pytest.mark.parametrize("minutes", [0, 30, 90, -60])
def test_grant_minutes(minutes: int) -> None:
    with pytest.raises(BusinessRuleViolation) as error:
        _account().grant(minutes, "지급", today=TODAY)
    assert error.value.code == "invalid_balance_minutes"


def test_reason_required() -> None:
    for reason in ("", "   ", "가" * 101):
        with pytest.raises(BusinessRuleViolation) as error:
            _account().grant(60, reason, today=TODAY)
        assert error.value.code == "invalid_balance_reason"


def test_expired_account() -> None:
    account = _account(valid_until=TODAY)
    account.grant(120, "지급", today=TODAY)  # 종료일 당일까지 사용 가능
    tomorrow = date(2026, 11, 12)
    with pytest.raises(BusinessRuleViolation) as grant:
        account.grant(60, "지급", today=tomorrow)
    assert grant.value.code == "balance_account_expired"
    with pytest.raises(BusinessRuleViolation):
        account.adjust(60, "추가", today=tomorrow)
    account.adjust(-60, "만료 정리", today=tomorrow)
    with pytest.raises(BusinessRuleViolation):
        account.adjust(0, "영", today=TODAY)


def test_validity_inside_cohort() -> None:
    account = _account()
    account.change_validity(date(2026, 12, 1), date(2026, 12, 1), **COHORT)  # 같은 날 가능
    assert (account.valid_from, account.valid_until) == (date(2026, 12, 1), date(2026, 12, 1))
    with pytest.raises(BusinessRuleViolation) as outside:
        account.change_validity(date(2026, 10, 31), date(2026, 12, 1), **COHORT)
    assert outside.value.code == "balance_validity_outside_cohort"
    with pytest.raises(BusinessRuleViolation):
        ensure_validity(date(2027, 4, 30), date(2027, 5, 1), **COHORT)
    with pytest.raises(BusinessRuleViolation) as reverse:
        ensure_validity(date(2026, 12, 2), date(2026, 12, 1), **COHORT)
    assert reverse.value.code == "invalid_balance_validity"

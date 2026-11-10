from datetime import date, time
from typing import Any

import pytest

from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def settings(**overrides: Any) -> CohortMentoringSettings:
    values: dict[str, Any] = {"cohort_id": new_id(), "allow_1_on_1": True}
    values.update(overrides)
    return CohortMentoringSettings(**values)


def test_valid_settings_and_change() -> None:
    current = settings(default_1on1_minutes=120, allowed_duration=60, min_lead_hours=6)
    changed = current.changed({"max_pending_requests": 3, "allow_team_mentoring": True})
    assert (changed.id, changed.max_pending_requests) == (current.id, 3)
    with pytest.raises(BusinessRuleViolation) as exc:
        current.changed({"cohort_id": new_id()})
    assert exc.value.code == "invalid_settings_field"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"allow_1_on_1": False}, "mentoring_mode_required"),
        ({"allowed_duration": 45}, "invalid_allowed_duration"),
        ({"allowed_duration": 90}, "invalid_allowed_duration"),
        ({"min_lead_hours": 48}, "invalid_min_lead_hours"),
        ({"min_lead_hours": 0}, "invalid_min_lead_hours"),
        ({"max_pending_requests": 0}, "invalid_max_pending_requests"),
        ({"max_pending_requests": 4}, "invalid_max_pending_requests"),
        ({"default_1on1_minutes": 90}, "invalid_default_minutes"),
        ({"default_team_minutes": -60}, "invalid_default_minutes"),
    ],
)
def test_settings_rules(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        settings(**overrides)
    assert exc.value.code == code


def block(start: date, end: date, t1: time, t2: time, **kw: Any) -> MentoringBlockTime:
    return MentoringBlockTime(
        cohort_id=new_id(), period_start=start, period_end=end, start_time=t1, end_time=t2, **kw
    )


NOV = (date(2026, 11, 1), date(2026, 11, 30))


def test_block_validation_and_reason() -> None:
    assert block(*NOV, time(9), time(18), reason="  ").reason is None
    for args, code in (
        ((date(2026, 12, 1), date(2026, 11, 1), time(9), time(18)), "invalid_block_period"),
        ((*NOV, time(18), time(9)), "invalid_block_time"),
        ((*NOV, time(9), time(9)), "invalid_block_time"),
    ):
        with pytest.raises(BusinessRuleViolation) as exc:
            block(*args)
        assert exc.value.code == code
    with pytest.raises(BusinessRuleViolation) as reason:
        block(*NOV, time(9), time(18), reason="가" * 201)
    assert reason.value.code == "invalid_block_reason"


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        ((*NOV, time(12), time(18)), False),  # 시간대가 맞닿기만 함
        ((date(2026, 12, 1), date(2026, 12, 31), time(9), time(12)), False),  # 기간이 다름
        ((date(2026, 11, 30), date(2026, 12, 5), time(11), time(13)), True),
        ((date(2026, 10, 1), date(2026, 11, 1), time(8), time(10)), True),  # 경계일 겹침
    ],
)
def test_block_overlap(other: tuple[date, date, time, time], expected: bool) -> None:
    assert block(*NOV, time(9), time(12)).overlaps(block(*other)) is expected


def test_block_applies_only_on_business_days_in_period() -> None:
    b = block(*NOV, time(9), time(18))
    assert b.applies_on(date(2026, 11, 2), is_business_day=True)
    assert not b.applies_on(date(2026, 11, 7), is_business_day=False)  # 주말·공휴일
    assert not b.applies_on(date(2026, 12, 1), is_business_day=True)  # 기간 밖


def test_holiday_name() -> None:
    assert MentoringHoliday(holiday_date=date(2026, 11, 20), name=" 휴무 ").name == "휴무"
    with pytest.raises(BusinessRuleViolation):
        MentoringHoliday(holiday_date=date(2026, 11, 20), name=" ")

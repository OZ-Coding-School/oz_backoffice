from datetime import UTC, date, datetime, time

import pytest

from app.shared.time import business_date
from app.shared.value_objects import DateRange, Email, Minutes, TimeRange

pytestmark = pytest.mark.unit


def test_minutes_arithmetic_and_non_negative() -> None:
    assert Minutes(30) + Minutes(30) == Minutes(60)
    assert Minutes(60) - Minutes(30) == Minutes(30)
    with pytest.raises(ValueError, match="음수"):
        Minutes(30) - Minutes(60)


def test_date_range_contains_and_overlaps() -> None:
    november = DateRange(date(2026, 11, 1), date(2026, 11, 30))
    assert november.contains(date(2026, 11, 30))
    assert not november.contains(date(2026, 12, 1))
    assert november.overlaps(DateRange(date(2026, 11, 30), date(2026, 12, 5)))
    assert not november.overlaps(DateRange(date(2026, 12, 1), date(2026, 12, 5)))
    with pytest.raises(ValueError, match="시작일"):
        DateRange(date(2026, 12, 1), date(2026, 11, 1))


def test_time_range_is_half_open() -> None:
    morning = TimeRange(time(9), time(12))
    assert morning.contains(TimeRange(time(9), time(12)))
    assert not morning.overlaps(TimeRange(time(12), time(13)))
    assert morning.overlaps(TimeRange(time(11, 30), time(13)))


def test_email_is_normalized_to_lowercase() -> None:
    email = Email("  Kim@NextRunners.co.kr ")
    assert email.value == "kim@nextrunners.co.kr"
    assert email.domain == "nextrunners.co.kr"
    with pytest.raises(ValueError, match="유효하지 않은 이메일"):
        Email("not-an-email")


def test_business_date_uses_kst_boundary() -> None:
    # UTC 15:30 = KST 다음날 00:30
    assert business_date(datetime(2026, 11, 4, 15, 30, tzinfo=UTC)) == date(2026, 11, 5)
    with pytest.raises(ValueError, match="tz-aware"):
        business_date(datetime(2026, 11, 4, 15, 30))

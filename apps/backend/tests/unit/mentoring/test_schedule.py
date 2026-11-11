"""멘토 불가 시간·기수 운영시간 도메인 규칙 (A37)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.contexts.mentoring.domain.schedule import (
    MentorUnavailablePeriod,
    mask_to_weekdays,
    weekdays_to_mask,
)
from app.contexts.mentoring.domain.settings import CohortMentoringSettings, OperatingHours
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id
from app.shared.time import KST

pytestmark = pytest.mark.unit

MENTOR = new_id()
DAILY = UnavailableRepeat.DAILY
WEEKLY = UnavailableRepeat.WEEKLY


def kst(day: int, hour: int, minute: int = 0, month: int = 11) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=KST)


def _period(**overrides: Any) -> MentorUnavailablePeriod:
    values: dict[str, Any] = {"mentor_id": MENTOR, "starts_at": kst(23, 19), "ends_at": kst(23, 22)}
    values.update(overrides)
    return MentorUnavailablePeriod(**values)


def _local(spans: list[tuple[datetime, datetime]]) -> list[tuple[str, str]]:
    return [
        (s.astimezone(KST).strftime("%m-%d %H:%M"), e.astimezone(KST).strftime("%m-%d %H:%M"))
        for s, e in spans
    ]


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"starts_at": kst(23, 19, 15)}, "invalid_slot_boundary"),
        ({"ends_at": kst(23, 19)}, "invalid_unavailable_range"),
        ({"starts_at": datetime(2026, 11, 23, 19)}, "invalid_unavailable_range"),  # 시간대 없음
        ({"weekdays": frozenset({1})}, "invalid_repeat_rule"),  # 일회성에 요일
        ({"repeat_until": date(2026, 12, 1)}, "invalid_repeat_rule"),  # 일회성에 종료일
        ({"repeat": WEEKLY}, "invalid_repeat_rule"),  # 매주인데 요일 없음
        ({"repeat": WEEKLY, "weekdays": frozenset({8})}, "invalid_repeat_rule"),
        ({"repeat": DAILY, "weekdays": frozenset({1})}, "invalid_repeat_rule"),
        ({"repeat": DAILY, "ends_at": kst(24, 19, 30)}, "invalid_repeat_rule"),  # 24시간 초과
        ({"repeat": DAILY, "repeat_until": date(2026, 11, 22)}, "invalid_repeat_rule"),
        ({"category": "가" * 31}, "invalid_schedule_text"),
        ({"reason": "가" * 201}, "invalid_schedule_text"),
    ],
)
def test_period_rules(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as error:
        _period(**overrides)
    assert error.value.code == code


def test_period_normalizes_and_cleans() -> None:
    period = _period(category="  근무 ", reason="   ")
    assert period.starts_at.tzinfo is UTC
    assert period.starts_at == datetime(2026, 11, 23, 10, tzinfo=UTC)
    assert (period.category, period.reason) == ("근무", None)
    # 반복 한 회차는 24시간까지 된다 (매일 종일)
    _period(repeat=DAILY, starts_at=kst(23, 0), ends_at=kst(24, 0))


def test_all_day_once_and_changeable() -> None:
    period = MentorUnavailablePeriod.for_dates(
        mentor_id=MENTOR, start_date=date(2026, 12, 1), end_date=date(2026, 12, 7)
    )
    assert period.is_all_day
    assert (period.starts_at, period.ends_at) == (
        datetime(2026, 11, 30, 15, tzinfo=UTC),
        datetime(2026, 12, 7, 15, tzinfo=UTC),
    )
    period.ensure_changeable(datetime(2026, 11, 30, 14, 59, tzinfo=UTC))
    with pytest.raises(BusinessRuleViolation) as started:
        period.ensure_changeable(datetime(2026, 11, 30, 15, tzinfo=UTC))
    assert started.value.code == "unavailable_period_started"
    with pytest.raises(BusinessRuleViolation):
        MentorUnavailablePeriod.for_dates(
            mentor_id=MENTOR, start_date=date(2026, 12, 2), end_date=date(2026, 12, 1)
        )
    # 반복은 이미 시작됐어도 바꿀 수 있다
    _period(repeat=DAILY).ensure_changeable(kst(30, 0))


def test_is_finished() -> None:
    once = _period()
    assert not once.is_finished(kst(23, 21))
    assert once.is_finished(kst(23, 22))
    daily = _period(repeat=DAILY, repeat_until=date(2026, 11, 25))
    assert not daily.is_finished(kst(25, 23))
    assert daily.is_finished(kst(26, 0))
    assert not _period(repeat=DAILY).is_finished(kst(30, 0, month=12))


def test_once_occurrences() -> None:
    period = _period()
    assert _local(list(period.occurrences(kst(23, 0), kst(24, 0)))) == [
        ("11-23 19:00", "11-23 22:00")
    ]
    assert list(period.occurrences(kst(23, 22), kst(24, 0))) == []  # 맞닿음은 제외


def test_daily_occurrences_cross_midnight_and_until() -> None:
    sleep = _period(
        repeat=DAILY,
        starts_at=kst(23, 23),
        ends_at=kst(24, 7),
        repeat_until=date(2026, 11, 25),
    )
    # 11/24 하루를 보면 전날 밤(23일 23시) 회차와 그날 밤 회차가 걸린다
    assert _local(list(sleep.occurrences(kst(24, 0), kst(25, 0)))) == [
        ("11-23 23:00", "11-24 07:00"),
        ("11-24 23:00", "11-25 07:00"),
    ]
    # 반복 종료일(25일) 회차까지, 기준 회차 전은 없다
    assert _local(list(sleep.occurrences(kst(20, 0), kst(30, 0)))) == [
        ("11-23 23:00", "11-24 07:00"),
        ("11-24 23:00", "11-25 07:00"),
        ("11-25 23:00", "11-26 07:00"),
    ]


def test_weekly_occurrences_over_month_end() -> None:
    work = _period(
        repeat=WEEKLY,
        weekdays=frozenset({1, 3, 5}),  # 월·수·금
        starts_at=kst(27, 9),  # 금요일 기준
        ends_at=kst(27, 18),
    )
    assert _local(list(work.occurrences(kst(26, 0), kst(3, 0, month=12)))) == [
        ("11-27 09:00", "11-27 18:00"),  # 금 (기준 회차, 26일 목은 없음)
        ("11-30 09:00", "11-30 18:00"),  # 월
        ("12-02 09:00", "12-02 18:00"),  # 수
    ]


def test_weekday_mask_round_trip() -> None:
    assert weekdays_to_mask(frozenset({1, 7})) == 65
    assert mask_to_weekdays(65) == frozenset({1, 7})
    assert mask_to_weekdays(0) == frozenset()


def test_revised_limits_fields() -> None:
    revised = _period().revised({"ends_at": kst(23, 23)})
    assert revised.ends_at == datetime(2026, 11, 23, 14, tzinfo=UTC)
    with pytest.raises(BusinessRuleViolation):
        _period().revised({"mentor_id": new_id()})


def test_operating_hours() -> None:
    hours = OperatingHours.of("10:00", "24:00")
    assert (hours.start_minute, hours.end_minute) == (600, 1440)
    assert OperatingHours.label(1440) == "24:00"
    for start, end in (("10:15", "19:00"), ("19:00", "10:00"), ("00:00", "24:30"), ("ab", "19:00")):
        with pytest.raises(BusinessRuleViolation) as error:
            OperatingHours.of(start, end)
        assert error.value.code == "invalid_operating_hours"
    settings = CohortMentoringSettings(cohort_id=new_id(), allow_1_on_1=True)
    assert settings.weekday_hours == OperatingHours(start_minute=600, end_minute=1140)
    assert settings.weekend_hours is None
    changed = settings.changed({"weekend_hours": OperatingHours.of("13:00", "17:00")})
    assert changed.weekend_hours == OperatingHours(start_minute=780, end_minute=1020)


def test_mentor_accepting_switch() -> None:
    mentor = Mentor(user_id=new_id())
    assert not mentor.accepting_requests
    mentor.set_accepting(True)
    mentor.deactivate()
    assert not mentor.accepting_requests  # 비활성화하면 꺼진다
    with pytest.raises(BusinessRuleViolation) as inactive:
        mentor.set_accepting(True)
    assert inactive.value.code == "mentor_inactive"
    mentor.set_accepting(False)

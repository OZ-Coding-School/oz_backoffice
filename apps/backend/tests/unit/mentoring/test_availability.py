"""신청 가능 시간 계산 (A37): 운영시간 − 불가 시간 − 금지 시간대 − 세션 − 신청 마감."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest

from app.contexts.mentoring.domain.availability import (
    AssignmentRange,
    Interval,
    available_intervals,
    subtract,
)
from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    OperatingHours,
)
from app.shared.ids import new_id
from app.shared.time import KST

pytestmark = pytest.mark.unit

MENTOR = new_id()
COHORT = new_id()
# 2026-11-16(월) ~ 11-22(일)
MON, TUE, SAT, SUN = date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 21), date(2026, 11, 22)
WEEK = [MON + timedelta(days=i) for i in range(7)]
BUSINESS = set(WEEK[:5])
EARLY = datetime(2026, 11, 1, tzinfo=UTC)  # 마감에 걸리지 않는 '지금'


def kst(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), KST)


def _settings(**overrides: Any) -> CohortMentoringSettings:
    values: dict[str, Any] = {"cohort_id": COHORT, "allow_1_on_1": True, "allowed_duration": 30}
    values.update(overrides)
    return CohortMentoringSettings(**values)


def _run(days: list[date], **overrides: Any) -> list[tuple[str, str]]:
    values: dict[str, Any] = {
        "days": days,
        "settings": _settings(),
        "business_days": BUSINESS,
        "assignments": [AssignmentRange(date(2026, 11, 1), None)],
        "unavailable": [],
        "blocks": [],
        "busy": [],
        "now": EARLY,
    }
    values.update(overrides)
    return [
        (i.start.astimezone(KST).strftime("%d %H:%M"), i.end.astimezone(KST).strftime("%d %H:%M"))
        for i in available_intervals(**values)
    ]


def test_operating_hours_weekday_and_weekend() -> None:
    assert _run([MON, SAT]) == [("16 10:00", "16 19:00")]  # 주말 운영 안 함 (기본)
    weekend = _settings(weekend_hours=OperatingHours.of("13:00", "17:00"))
    assert _run([SAT], settings=weekend) == [("21 13:00", "21 17:00")]
    # 공휴일(영업일 아님)은 주말 시간을 쓴다
    assert _run([MON], settings=weekend, business_days=set()) == [("16 13:00", "16 17:00")]
    assert _run([MON], settings=_settings(weekday_hours=None)) == []


def test_late_hours_merge_across_midnight() -> None:
    night = _settings(
        weekday_hours=OperatingHours.of("20:00", "24:00"),
        weekend_hours=OperatingHours.of("00:00", "02:00"),
    )
    # 금요일 20~24시와 토요일 00~02시는 이어진다
    assert _run([WEEK[4], SAT], settings=night) == [("20 20:00", "21 02:00")]


def test_unavailable_once_daily_weekly() -> None:
    lunch = MentorUnavailablePeriod(
        mentor_id=MENTOR,
        repeat=UnavailableRepeat.DAILY,
        starts_at=kst(date(2026, 11, 1), 12),
        ends_at=kst(date(2026, 11, 1), 13),
    )
    meeting = MentorUnavailablePeriod(
        mentor_id=MENTOR,
        repeat=UnavailableRepeat.WEEKLY,
        weekdays=frozenset({2}),
        starts_at=kst(date(2026, 11, 3), 15),
        ends_at=kst(date(2026, 11, 3), 16, 30),
    )
    dentist = MentorUnavailablePeriod(
        mentor_id=MENTOR, starts_at=kst(MON, 17), ends_at=kst(MON, 20)
    )
    assert _run([MON, TUE], unavailable=[lunch, meeting, dentist]) == [
        ("16 10:00", "16 12:00"),
        ("16 13:00", "16 17:00"),
        ("17 10:00", "17 12:00"),
        ("17 13:00", "17 15:00"),
        ("17 16:30", "17 19:00"),
    ]


def test_overnight_unavailable_from_previous_day() -> None:
    night = MentorUnavailablePeriod(
        mentor_id=MENTOR,
        repeat=UnavailableRepeat.DAILY,
        starts_at=kst(date(2026, 11, 1), 22),
        ends_at=kst(date(2026, 11, 2), 11),  # 매일 22시 ~ 다음 날 11시
    )
    assert _run([MON], unavailable=[night]) == [("16 11:00", "16 19:00")]


def test_block_times_only_on_business_days() -> None:
    block = MentoringBlockTime(
        cohort_id=COHORT,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 30),
        start_time=time(10),
        end_time=time(14),
    )
    everyday = _settings(weekend_hours=OperatingHours.of("10:00", "19:00"))
    assert _run([MON, SAT], settings=everyday, blocks=[block]) == [
        ("16 14:00", "16 19:00"),
        ("21 10:00", "21 19:00"),  # 주말에는 적용하지 않는다
    ]


def test_sessions_lead_time_and_minimum_length() -> None:
    session = Interval(kst(MON, 14).astimezone(UTC), kst(MON, 15).astimezone(UTC))
    assert _run([MON], busy=[session]) == [("16 10:00", "16 14:00"), ("16 15:00", "16 19:00")]
    # 지금 월 07:10, 마감 6시간 → 13:10 이후, 30분 경계로 올려 13:30부터
    now = kst(MON, 7, 10).astimezone(UTC)
    assert _run([MON], now=now, settings=_settings(min_lead_hours=6)) == [("16 13:30", "16 19:00")]
    # 진행 단위(60분)보다 짧은 구간은 버린다
    short = MentorUnavailablePeriod(
        mentor_id=MENTOR, starts_at=kst(MON, 10, 30), ends_at=kst(MON, 19)
    )
    assert _run([MON], unavailable=[short], settings=_settings(allowed_duration=60)) == []
    assert _run([MON], unavailable=[short]) == [("16 10:00", "16 10:30")]


def test_assignment_ranges() -> None:
    ranges = [AssignmentRange(TUE, TUE), AssignmentRange(date(2026, 11, 19), None)]
    assert [s for s, _ in _run(WEEK[:5], assignments=ranges)] == [
        "17 10:00",
        "19 10:00",
        "20 10:00",
    ]
    assert _run([MON], assignments=[]) == []


def test_subtract_edges() -> None:
    a = Interval(kst(MON, 10), kst(MON, 12))
    assert subtract([a], [Interval(kst(MON, 12), kst(MON, 13))]) == [a]  # 맞닿음
    assert subtract([a], [Interval(kst(MON, 9), kst(MON, 13))]) == []
    assert subtract([a], [Interval(kst(MON, 11), kst(MON, 11))]) == [a]  # 길이 0

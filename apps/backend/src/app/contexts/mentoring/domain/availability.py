"""신청 가능 시간 계산 (decisions A37, 순수 함수).

신청 가능 시간 = 기수 운영시간 − 멘토 불가 시간 − 기수 금지 시간대 − 이미 잡힌 세션 − 신청 마감.
- 날짜는 한국 시각 기준이고, 멘토의 그 기수 활성 배정 기간(합집합) 안의 날짜만 연다.
- 운영시간은 영업일(평일·비공휴일)이면 평일 시간, 아니면 주말·공휴일 시간을 쓴다.
- 금지 시간대는 영업일에만 적용한다(A34).
- 신청 마감(지금 + min_lead_hours) 전 시각은 빼고, 시작은 30분 경계로 올린다.
- 이어지는 구간은 합치고(자정을 넘어도), 진행 단위보다 짧은 구간은 버린다.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.contexts.mentoring.domain.schedule import SLOT_MINUTES, MentorUnavailablePeriod
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    OperatingHours,
)
from app.shared.time import KST


@dataclass(frozen=True, slots=True)
class Interval:
    """[start, end) — UTC."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True, slots=True)
class AssignmentRange:
    start: date
    end: date | None  # None = 기한 없음

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


def _at(day: date, minute: int) -> datetime:
    """그날 한국 시각 00:00부터 minute분 뒤 (1440이면 다음 날 00:00)."""
    return (datetime.combine(day, time(), KST) + timedelta(minutes=minute)).astimezone(UTC)


def _merge(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for current in sorted(intervals, key=lambda i: i.start):
        if merged and current.start <= merged[-1].end:
            if current.end > merged[-1].end:
                merged[-1] = Interval(merged[-1].start, current.end)
        else:
            merged.append(current)
    return merged


def subtract(base: list[Interval], holes: Iterable[Interval]) -> list[Interval]:
    """base(겹치지 않고 정렬된 구간)에서 holes를 뺀다."""
    result = base
    for hole in _merge(h for h in holes if h.start < h.end):  # 길이 0인 구간은 무시
        next_result: list[Interval] = []
        for part in result:
            if hole.end <= part.start or part.end <= hole.start:
                next_result.append(part)
                continue
            if part.start < hole.start:
                next_result.append(Interval(part.start, hole.start))
            if hole.end < part.end:
                next_result.append(Interval(hole.end, part.end))
        result = next_result
    return result


def _ceil_to_slot(value: datetime) -> datetime:
    step = SLOT_MINUTES * 60
    seconds = value.timestamp()
    rounded = -(-seconds // step) * step
    return datetime.fromtimestamp(rounded, UTC)


def _hours_on(
    day: date, settings: CohortMentoringSettings, business_days: set[date]
) -> OperatingHours | None:
    return settings.weekday_hours if day in business_days else settings.weekend_hours


def available_intervals(
    *,
    days: list[date],
    settings: CohortMentoringSettings,
    business_days: set[date],
    assignments: list[AssignmentRange],
    unavailable: list[MentorUnavailablePeriod],
    blocks: list[MentoringBlockTime],
    busy: list[Interval],
    now: datetime,
) -> list[Interval]:
    """조회 날짜들(한국 날짜)의 신청 가능 구간 (UTC, 시작 순)."""
    opens: list[Interval] = []
    holes: list[Interval] = list(busy)
    for day in days:
        if not any(a.covers(day) for a in assignments):
            continue
        hours = _hours_on(day, settings, business_days)
        if hours is None:
            continue
        opens.append(Interval(_at(day, hours.start_minute), _at(day, hours.end_minute)))
        if day in business_days:
            holes.extend(
                Interval(
                    _at(day, b.start_time.hour * 60 + b.start_time.minute),
                    _at(day, b.end_time.hour * 60 + b.end_time.minute),
                )
                for b in blocks
                if b.applies_on(day, is_business_day=True)
            )
    if not opens:
        return []
    window = Interval(min(o.start for o in opens), max(o.end for o in opens))
    for period in unavailable:
        holes.extend(Interval(s, e) for s, e in period.occurrences(window.start, window.end))
    not_before = _ceil_to_slot(now + timedelta(hours=settings.min_lead_hours))
    holes.append(Interval(window.start, max(window.start, not_before)))
    free = subtract(_merge(opens), holes)
    return [i for i in free if i.minutes >= settings.allowed_duration]

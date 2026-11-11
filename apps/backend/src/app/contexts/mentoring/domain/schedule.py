"""멘토 불가 시간 (decisions A37).

멘토는 불가 시간만 등록하고 그 외는 가능으로 본다. 수강생은 기수 운영시간 안에서만 고른다.
- 일회성 / 매일 / 매주(요일 여러 개). 캘린더처럼 시작·종료 날짜시각(반복은 기준 회차)과 반복 규칙,
  반복 종료일(선택)로 둔다. 매주 반복은 기준 회차 날짜부터 고른 요일마다 같은 시각에 생긴다.
- 시각은 한국 시각 30분 경계. 자정을 넘겨도 되고 반복 한 회차는 24시간 이하다.
- 불가 시간끼리는 겹쳐도 된다. 일회성은 시작 전까지만 바꾸고, 반복은 언제든 바꾼다.
"""

import dataclasses
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.shared.domain import Entity
from app.shared.errors import BusinessRuleViolation
from app.shared.time import KST, business_date

SLOT_MINUTES = 30
MAX_OCCURRENCE = timedelta(days=1)
REASON_MAX_LENGTH = 200
CATEGORY_MAX_LENGTH = 30
EDITABLE_FIELDS = frozenset(
    {"repeat", "starts_at", "ends_at", "weekdays", "repeat_until", "category", "reason"}
)


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def _on_boundary(value: datetime) -> bool:
    local = value.astimezone(KST)
    return local.minute % SLOT_MINUTES == 0 and local.second == 0 and local.microsecond == 0


def _clean(value: str | None, limit: int, label: str) -> str | None:
    text = (value or "").strip()
    _rule(len(text) <= limit, f"{label}은(는) {limit}자 이하여야 합니다.", "invalid_schedule_text")
    return text or None


def weekdays_to_mask(weekdays: frozenset[int]) -> int:
    return sum(1 << (day - 1) for day in weekdays)


def mask_to_weekdays(mask: int) -> frozenset[int]:
    return frozenset(day for day in range(1, 8) if mask & (1 << (day - 1)))


@dataclass(kw_only=True, eq=False)
class MentorUnavailablePeriod(Entity):
    """불가 시간. 시각은 UTC로 정규화한다. weekdays는 1=월 … 7=일(매주 반복만)."""

    mentor_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    repeat: UnavailableRepeat = UnavailableRepeat.ONCE
    weekdays: frozenset[int] = frozenset()
    repeat_until: date | None = None
    category: str | None = None
    reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _rule(
            self.starts_at.tzinfo is not None and self.ends_at.tzinfo is not None,
            "시각에 시간대가 필요합니다.",
            "invalid_unavailable_range",
        )
        self.starts_at = self.starts_at.astimezone(UTC)
        self.ends_at = self.ends_at.astimezone(UTC)
        self.weekdays = frozenset(self.weekdays)
        _rule(
            _on_boundary(self.starts_at) and _on_boundary(self.ends_at),
            "불가 시간은 정각 또는 30분 단위로 입력합니다.",
            "invalid_slot_boundary",
        )
        _rule(
            self.starts_at < self.ends_at,
            "불가 시간의 시작이 끝보다 빨라야 합니다.",
            "invalid_unavailable_range",
        )
        if self.repeat is UnavailableRepeat.ONCE:
            _rule(
                not self.weekdays and self.repeat_until is None,
                "일회성 불가 시간에는 반복 요일·종료일을 넣지 않습니다.",
                "invalid_repeat_rule",
            )
        else:
            _rule(
                self.ends_at - self.starts_at <= MAX_OCCURRENCE,
                "반복 불가 시간의 한 회차는 24시간 이하여야 합니다.",
                "invalid_repeat_rule",
            )
            _rule(
                self.repeat_until is None or self.repeat_until >= self.start_date,
                "반복 종료일이 시작일보다 빠릅니다.",
                "invalid_repeat_rule",
            )
        if self.repeat is UnavailableRepeat.WEEKLY:
            _rule(
                bool(self.weekdays) and self.weekdays <= set(range(1, 8)),
                "매주 반복은 요일(1=월~7=일)을 하나 이상 고릅니다.",
                "invalid_repeat_rule",
            )
        elif self.repeat is UnavailableRepeat.DAILY:
            _rule(not self.weekdays, "매일 반복에는 요일을 넣지 않습니다.", "invalid_repeat_rule")
        self.category = _clean(self.category, CATEGORY_MAX_LENGTH, "분류")
        self.reason = _clean(self.reason, REASON_MAX_LENGTH, "메모")

    @classmethod
    def for_dates(
        cls, *, mentor_id: uuid.UUID, start_date: date, end_date: date, **extra: Any
    ) -> "MentorUnavailablePeriod":
        """일회성 종일: 시작일 00:00 ~ 종료일 다음 날 00:00 (한국 시각)."""
        _rule(
            start_date <= end_date,
            "불가 일정의 시작일이 종료일보다 늦습니다.",
            "invalid_unavailable_range",
        )
        return cls(
            mentor_id=mentor_id,
            starts_at=datetime.combine(start_date, time(), KST),
            ends_at=datetime.combine(end_date + timedelta(days=1), time(), KST),
            **extra,
        )

    @property
    def start_date(self) -> date:
        return business_date(self.starts_at)

    @property
    def is_recurring(self) -> bool:
        return self.repeat is not UnavailableRepeat.ONCE

    @property
    def is_all_day(self) -> bool:
        start, end = self.starts_at.astimezone(KST), self.ends_at.astimezone(KST)
        return start.time() == time() and end.time() == time()

    def is_finished(self, now: datetime) -> bool:
        """더 생길 회차가 없는지 (일정 목록에서 지난 것 거르기)."""
        if not self.is_recurring:
            return self.ends_at <= now
        return self.repeat_until is not None and self.repeat_until < business_date(now)

    def ensure_changeable(self, now: datetime) -> None:
        """일회성은 시작 전까지만 등록·수정·삭제한다. 반복은 언제든 바꾼다."""
        _rule(
            self.is_recurring or now < self.starts_at,
            "이미 시작된 일회성 불가 일정은 등록·수정·삭제할 수 없습니다.",
            "unavailable_period_started",
        )

    def revised(self, values: dict[str, Any]) -> "MentorUnavailablePeriod":
        _rule(set(values) <= EDITABLE_FIELDS, "바꿀 수 없는 항목입니다.", "invalid_schedule_field")
        return dataclasses.replace(self, **values)

    def occurrences(self, start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
        """[start, end)와 겹치는 회차의 (시작, 끝)을 UTC로 시작 순서대로 낸다."""
        if not self.is_recurring:
            if self.starts_at < end and start < self.ends_at:
                yield self.starts_at, self.ends_at
            return
        local_start = self.starts_at.astimezone(KST)
        length = self.ends_at - self.starts_at
        # 자정을 넘는 회차가 있으므로 하루 앞에서부터 본다
        day = max(self.start_date, business_date(start) - timedelta(days=1))
        last = business_date(end)
        if self.repeat_until is not None:
            last = min(last, self.repeat_until)
        while day <= last:
            if self.repeat is UnavailableRepeat.DAILY or day.isoweekday() in self.weekdays:
                occurrence = datetime.combine(day, local_start.timetz())
                if occurrence < end and start < occurrence + length:
                    yield occurrence.astimezone(UTC), (occurrence + length).astimezone(UTC)
            day += timedelta(days=1)

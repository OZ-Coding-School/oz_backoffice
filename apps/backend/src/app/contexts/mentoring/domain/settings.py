"""기수 멘토링 설정·금지 시간대·추가 휴일 (decisions A34).

- 설정 값: 진행 단위 30·60분, 신청 마감 6·12·24시간, 대기 신청 1~3건, 기본 지급 시간 60분 단위,
  팀·1:1 중 하나 이상 허용.
- 운영시간(A37): 평일, 주말·공휴일 각각 시작~끝(한국 시각, 30분 경계, 24:00까지)
  또는 운영 안 함(None).
  수강생은 이 시간 안에서만 신청한다. 기본값은 평일 10:00~19:00, 주말·공휴일 운영 안 함.
- 금지 시간대: 기간(시작일~종료일) 안의 평일(월~금)에만 적용하고 주말·공휴일에는 적용하지 않는다.
  같은 기수에서 기간과 시간대가 모두 겹치면 안 된다.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation

ALLOWED_DURATIONS = (30, 60)
LEAD_HOURS_CHOICES = (6, 12, 24)
MAX_PENDING_RANGE = (1, 3)
GRANT_UNIT_MINUTES = 60
REASON_MAX_LENGTH = 200
HOLIDAY_NAME_MAX_LENGTH = 50

SETTINGS_FIELDS = frozenset(
    {
        "allow_team_mentoring",
        "allow_1_on_1",
        "default_1on1_minutes",
        "default_team_minutes",
        "min_lead_hours",
        "allowed_duration",
        "max_pending_requests",
        "weekday_hours",
        "weekend_hours",
    }
)
MINUTES_PER_DAY = 24 * 60


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


@dataclass(frozen=True, slots=True)
class OperatingHours:
    """하루 운영시간. 자정부터 지난 분(0~1440)으로 두어 24:00을 표현한다."""

    start_minute: int
    end_minute: int

    def __post_init__(self) -> None:
        _rule(
            0 <= self.start_minute < self.end_minute <= MINUTES_PER_DAY
            and self.start_minute % 30 == 0
            and self.end_minute % 30 == 0,
            "운영시간은 00:00~24:00 안에서 30분 단위로, 시작이 끝보다 빨라야 합니다.",
            "invalid_operating_hours",
        )

    @classmethod
    def of(cls, start: str, end: str) -> "OperatingHours":
        """ "HH:MM" (끝은 "24:00" 가능)."""
        return cls(start_minute=_minutes(start), end_minute=_minutes(end))

    @staticmethod
    def label(minute: int) -> str:
        return f"{minute // 60:02d}:{minute % 60:02d}"


def _minutes(text: str) -> int:
    hour, _, minute = text.partition(":")
    _rule(
        hour.isdigit() and minute.isdigit() and len(minute) == 2,
        "시각은 HH:MM 형식입니다.",
        "invalid_operating_hours",
    )
    return int(hour) * 60 + int(minute)


DEFAULT_WEEKDAY_HOURS = OperatingHours(start_minute=10 * 60, end_minute=19 * 60)


@dataclass(kw_only=True, eq=False)
class CohortMentoringSettings(AggregateRoot):
    cohort_id: uuid.UUID
    allow_team_mentoring: bool = False
    allow_1_on_1: bool = False
    default_1on1_minutes: int = 0
    default_team_minutes: int = 0
    min_lead_hours: int = 24
    allowed_duration: int = 30
    max_pending_requests: int = 1
    weekday_hours: OperatingHours | None = DEFAULT_WEEKDAY_HOURS
    weekend_hours: OperatingHours | None = None  # 주말·공휴일, None = 운영 안 함
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _rule(
            self.allow_team_mentoring or self.allow_1_on_1,
            "팀 멘토링과 1:1 멘토링 중 하나 이상을 허용해야 합니다.",
            "mentoring_mode_required",
        )
        _rule(
            self.allowed_duration in ALLOWED_DURATIONS,
            "진행 단위는 30분 또는 60분입니다.",
            "invalid_allowed_duration",
        )
        _rule(
            self.min_lead_hours in LEAD_HOURS_CHOICES,
            "신청 마감은 6·12·24시간 중에서 고릅니다.",
            "invalid_min_lead_hours",
        )
        low, high = MAX_PENDING_RANGE
        _rule(
            low <= self.max_pending_requests <= high,
            f"대기 중 신청은 {low}~{high}건입니다.",
            "invalid_max_pending_requests",
        )
        for minutes in (self.default_1on1_minutes, self.default_team_minutes):
            _rule(
                minutes >= 0 and minutes % GRANT_UNIT_MINUTES == 0,
                "기본 지급 시간은 시간 단위(60분 단위)로 설정합니다.",
                "invalid_default_minutes",
            )

    def changed(self, values: dict[str, Any]) -> "CohortMentoringSettings":
        """설정 값을 바꾼 새 설정(같은 검증). 진행 중인 신청에는 소급하지 않는다."""
        _rule(set(values) <= SETTINGS_FIELDS, "바꿀 수 없는 항목입니다.", "invalid_settings_field")
        return dataclasses.replace(self, **values)


@dataclass(kw_only=True, eq=False)
class MentoringBlockTime(Entity):
    cohort_id: uuid.UUID
    period_start: date
    period_end: date
    start_time: time
    end_time: time
    reason: str | None = None

    def __post_init__(self) -> None:
        _rule(
            self.period_start <= self.period_end,
            "금지 기간의 시작일이 종료일보다 늦습니다.",
            "invalid_block_period",
        )
        _rule(
            self.start_time < self.end_time,
            "금지 시작 시각은 끝 시각보다 빨라야 합니다.",
            "invalid_block_time",
        )
        reason = (self.reason or "").strip()
        _rule(
            len(reason) <= REASON_MAX_LENGTH,
            f"사유는 {REASON_MAX_LENGTH}자 이하여야 합니다.",
            "invalid_block_reason",
        )
        self.reason = reason or None

    def overlaps(self, other: "MentoringBlockTime") -> bool:
        """기간과 시간대가 모두 겹치는지 (같은 기수 안의 등록 제한)."""
        return (
            self.period_start <= other.period_end
            and other.period_start <= self.period_end
            and self.start_time < other.end_time
            and other.start_time < self.end_time
        )

    def applies_on(self, day: date, *, is_business_day: bool) -> bool:
        """그날 이 금지 시간대가 적용되는지. 평일(영업일)에만 적용한다."""
        return is_business_day and self.period_start <= day <= self.period_end

    def revised(self, values: dict[str, Any]) -> "MentoringBlockTime":
        allowed = {"period_start", "period_end", "start_time", "end_time", "reason"}
        _rule(set(values) <= allowed, "바꿀 수 없는 항목입니다.", "invalid_block_field")
        return dataclasses.replace(self, **values)


@dataclass(kw_only=True, eq=False)
class MentoringHoliday(Entity):
    """운영진이 등록하는 전사 공통 추가 휴일 (임시공휴일·휴무일)."""

    holiday_date: date
    name: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        _rule(
            0 < len(name) <= HOLIDAY_NAME_MAX_LENGTH,
            f"휴일 이름은 1~{HOLIDAY_NAME_MAX_LENGTH}자여야 합니다.",
            "invalid_holiday_name",
        )
        self.name = name

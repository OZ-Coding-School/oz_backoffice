"""공용 값 객체."""

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True, order=True)
class Minutes:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Minutes는 음수가 될 수 없습니다.")

    def __add__(self, other: "Minutes") -> "Minutes":
        return Minutes(self.value + other.value)

    def __sub__(self, other: "Minutes") -> "Minutes":
        return Minutes(self.value - other.value)


@dataclass(frozen=True, slots=True)
class DateRange:
    """양 끝을 포함하는 날짜 구간."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("DateRange 시작일이 종료일보다 늦습니다.")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def overlaps(self, other: "DateRange") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True, slots=True)
class TimeRange:
    """하루 안의 반열린 시간 구간 [start, end)."""

    start: time
    end: time

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("TimeRange 시작 시각이 종료 시각보다 같거나 늦습니다.")

    def contains(self, other: "TimeRange") -> bool:
        return self.start <= other.start and other.end <= self.end

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class Email:
    """소문자로 정규화된 이메일 (users.email check 제약과 일치)."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        local, sep, domain = normalized.partition("@")
        if not sep or not local or "." not in domain:
            raise ValueError(f"유효하지 않은 이메일: {self.value!r}")
        object.__setattr__(self, "value", normalized)

    @property
    def domain(self) -> str:
        return self.value.partition("@")[2]

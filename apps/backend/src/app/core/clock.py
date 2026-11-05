"""시각 주입. 도메인은 now를 인자로 받고, 서비스가 Clock에서 꺼내 넘긴다."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """테스트용 고정 시계."""

    def __init__(self, at: datetime) -> None:
        self.set(at)

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock에는 tz-aware datetime이 필요합니다.")
        self._at = at

"""영업일 판단 (decisions A34·B15).

평일(월~금)이면서 한국 공휴일(`holidays` 패키지: 법정공휴일·음력·대체공휴일)과 운영진이 등록한
추가 휴일이 아닌 날이 영업일이다. 금지 시간대는 영업일에만 적용한다.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache

import holidays

from app.contexts.mentoring.domain.repositories import MentoringHolidayRepository


class HolidaySource(StrEnum):
    PUBLIC = "PUBLIC"  # 법정공휴일 (holidays 패키지)
    CUSTOM = "CUSTOM"  # 운영진 등록


@dataclass(frozen=True, slots=True)
class Holiday:
    day: date
    name: str
    source: HolidaySource


@lru_cache(maxsize=32)
def _public(year: int) -> dict[date, str]:
    return dict(holidays.country_holidays("KR", years=year))


def public_holidays(start: date, end: date) -> list[Holiday]:
    found = []
    for year in range(start.year, end.year + 1):
        for day, name in _public(year).items():
            if start <= day <= end:
                found.append(Holiday(day, name, HolidaySource.PUBLIC))
    return sorted(found, key=lambda h: h.day)


class BusinessCalendar:
    def __init__(self, extra: MentoringHolidayRepository) -> None:
        self._extra = extra

    async def holidays_between(self, start: date, end: date) -> list[Holiday]:
        """법정공휴일과 추가 휴일 (날짜순, 같은 날은 둘 다)."""
        custom = [
            Holiday(h.holiday_date, h.name, HolidaySource.CUSTOM)
            for h in await self._extra.list_between(start, end)
        ]
        return sorted(public_holidays(start, end) + custom, key=lambda h: (h.day, h.source))

    async def business_days(self, start: date, end: date) -> set[date]:
        off = {h.day for h in await self.holidays_between(start, end)}
        days = set()
        day = start
        while day <= end:
            if day.weekday() < 5 and day not in off:
                days.add(day)
            day += timedelta(days=1)
        return days

    async def is_business_day(self, day: date) -> bool:
        return day in await self.business_days(day, day)

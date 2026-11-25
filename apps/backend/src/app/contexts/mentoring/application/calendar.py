"""영업일 판단 (decisions A34·A95).

평일(월~금)이면서 법정공휴일(특일 정보 API에서 받아 DB에 저장한 것)과 운영진이 등록한
추가 휴일이 아닌 날이 영업일이다. 받아 오지 못한 해는 법정공휴일이 없는 것으로 본다.
금지 시간대는 영업일에만 적용한다.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.contexts.mentoring.domain.repositories import (
    MentoringHolidayRepository,
    PublicHolidayRepository,
)


class HolidaySource(StrEnum):
    PUBLIC = "PUBLIC"  # 법정공휴일 (특일 정보 API)
    CUSTOM = "CUSTOM"  # 운영진 등록


@dataclass(frozen=True, slots=True)
class Holiday:
    day: date
    name: str
    source: HolidaySource


class BusinessCalendar:
    def __init__(self, extra: MentoringHolidayRepository, public: PublicHolidayRepository) -> None:
        self._extra = extra
        self._public = public

    async def holidays_between(self, start: date, end: date) -> list[Holiday]:
        """법정공휴일과 추가 휴일 (날짜순, 같은 날은 둘 다)."""
        public = [
            Holiday(h.holiday_date, h.name, HolidaySource.PUBLIC)
            for h in await self._public.list_between(start, end)
        ]
        custom = [
            Holiday(h.holiday_date, h.name, HolidaySource.CUSTOM)
            for h in await self._extra.list_between(start, end)
        ]
        return sorted(public + custom, key=lambda h: (h.day, h.source))

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

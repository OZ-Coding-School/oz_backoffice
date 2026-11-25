import uuid
from datetime import date

import pytest

from app.contexts.mentoring.application.calendar import BusinessCalendar, HolidaySource
from app.contexts.mentoring.domain.settings import MentoringHoliday, PublicHoliday
from tests.fakes.mentoring import InMemoryPublicHolidayRepository

pytestmark = pytest.mark.unit


class FakeHolidays:
    def __init__(self, *holidays: MentoringHoliday) -> None:
        self.items = list(holidays)

    async def list_between(self, start: date, end: date) -> list[MentoringHoliday]:
        return [h for h in self.items if start <= h.holiday_date <= end]

    async def add(self, holiday: MentoringHoliday) -> None: ...
    async def get(self, holiday_id: uuid.UUID) -> MentoringHoliday | None: ...
    async def get_by_date(self, day: date) -> MentoringHoliday | None: ...
    async def delete(self, holiday_id: uuid.UUID) -> None: ...


async def test_business_days_exclude_weekends_public_and_custom_holidays() -> None:
    calendar = BusinessCalendar(
        FakeHolidays(MentoringHoliday(holiday_date=date(2026, 11, 20), name="학원 휴무")),
        InMemoryPublicHolidayRepository(PublicHoliday(date(2026, 9, 24), "추석")),
    )
    assert await calendar.is_business_day(date(2026, 11, 19))  # 목요일
    assert not await calendar.is_business_day(date(2026, 11, 20))  # 추가 휴일(금)
    assert not await calendar.is_business_day(date(2026, 11, 21))  # 토요일
    assert not await calendar.is_business_day(date(2026, 9, 24))  # 법정공휴일(목)
    holidays = await calendar.holidays_between(date(2026, 9, 1), date(2026, 11, 30))
    assert [(h.day, h.source) for h in holidays] == [
        (date(2026, 9, 24), HolidaySource.PUBLIC),
        (date(2026, 11, 20), HolidaySource.CUSTOM),
    ]


async def test_year_not_synced_has_no_public_holidays() -> None:
    """받아 오지 못한 해는 법정공휴일이 없는 것으로 본다 (A95)."""
    calendar = BusinessCalendar(FakeHolidays(), InMemoryPublicHolidayRepository())
    assert await calendar.is_business_day(date(2026, 9, 24))

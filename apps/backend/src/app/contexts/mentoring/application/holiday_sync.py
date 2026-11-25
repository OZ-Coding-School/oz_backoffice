"""법정공휴일 동기화 (decisions A95·B16).

특일 정보 API에서 올해·내년 공휴일을 받아 그해를 응답 그대로 통째로 바꾼다(0건이면 비움).
두 해를 모두 받은 뒤 한 트랜잭션에서 저장하므로, 호출이 실패하면 어느 해도 바뀌지 않는다.
"""

from datetime import date
from typing import Protocol

from app.contexts.mentoring.domain.repositories import PublicHolidayRepository
from app.contexts.mentoring.domain.settings import PublicHoliday, PublicHolidaySync
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.time import business_date


class PublicHolidaySource(Protocol):
    async def fetch_year(self, year: int) -> list[tuple[date, str]]:
        """그해 공휴일 (날짜, 이름). 실패하면 ServiceUnavailableError(`holiday_sync_failed`)."""
        ...


class PublicHolidaySyncService:
    def __init__(
        self,
        *,
        source: PublicHolidaySource,
        holidays: PublicHolidayRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._source = source
        self._holidays = holidays
        self._uow = uow
        self._clock = clock

    def target_years(self) -> list[int]:
        """올해·내년 (한국 날짜 기준)."""
        year = business_date(self._clock.now()).year
        return [year, year + 1]

    async def sync(self) -> list[PublicHolidaySync]:
        fetched = {year: await self._source.fetch_year(year) for year in self.target_years()}
        now = self._clock.now()
        results = []
        async with self._uow:
            for year, items in fetched.items():
                unique = sorted(
                    {PublicHoliday(day, name.strip()) for day, name in items if day.year == year},
                    key=lambda h: (h.holiday_date, h.name),
                )
                await self._holidays.replace_year(year, unique, now)
                results.append(
                    PublicHolidaySync(year=year, synced_at=now, holiday_count=len(unique))
                )
        return results

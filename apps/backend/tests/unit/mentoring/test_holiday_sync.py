from datetime import UTC, date, datetime

import pytest

from app.contexts.mentoring.application.holiday_sync import PublicHolidaySyncService
from app.contexts.mentoring.domain.settings import PublicHoliday
from app.core.clock import FixedClock
from app.shared.errors import ServiceUnavailableError
from tests.fakes.mentoring import InMemoryPublicHolidayRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

# 2026-12-31 15:30 UTC = 2027-01-01 00:30 KST → 올해는 2027
NOW = datetime(2026, 12, 31, 15, 30, tzinfo=UTC)


class Source:
    def __init__(self, data: dict[int, list[tuple[date, str]]], fail: int | None = None) -> None:
        self.data = data
        self.fail = fail
        self.calls: list[int] = []

    async def fetch_year(self, year: int) -> list[tuple[date, str]]:
        self.calls.append(year)
        if year == self.fail:
            raise ServiceUnavailableError("실패", code="holiday_sync_failed")
        return self.data.get(year, [])


def service(source: Source, repo: InMemoryPublicHolidayRepository) -> PublicHolidaySyncService:
    return PublicHolidaySyncService(
        source=source, holidays=repo, uow=FakeUnitOfWork(), clock=FixedClock(NOW)
    )


async def test_syncs_this_and_next_year_by_kst_and_replaces_each_year() -> None:
    repo = InMemoryPublicHolidayRepository(
        PublicHoliday(date(2027, 3, 1), "삼일절"),
        PublicHoliday(date(2027, 6, 3), "취소된 임시공휴일"),
        PublicHoliday(date(2026, 12, 25), "기독탄신일"),  # 대상이 아닌 해는 그대로
    )
    source = Source(
        {
            2027: [
                (date(2027, 3, 1), "삼일절"),
                (date(2027, 5, 5), "어린이날"),
                (date(2027, 5, 5), "어린이날"),  # 중복은 하나로
                (date(2028, 1, 1), "다른 해"),  # 그해가 아닌 날은 버린다
            ],
            2028: [(date(2028, 1, 1), " 1월1일 ")],
        }
    )
    results = await service(source, repo).sync()

    assert source.calls == [2027, 2028]
    assert [(r.year, r.holiday_count, r.synced_at) for r in results] == [
        (2027, 2, NOW),
        (2028, 1, NOW),
    ]
    assert await repo.list_between(date(2026, 1, 1), date(2028, 12, 31)) == [
        PublicHoliday(date(2026, 12, 25), "기독탄신일"),
        PublicHoliday(date(2027, 3, 1), "삼일절"),
        PublicHoliday(date(2027, 5, 5), "어린이날"),
        PublicHoliday(date(2028, 1, 1), "1월1일"),
    ]


async def test_empty_response_clears_the_year() -> None:
    """응답 그대로 반영: 0건이면 그해를 비운다 (A95)."""
    repo = InMemoryPublicHolidayRepository(PublicHoliday(date(2028, 1, 1), "1월1일"))
    await service(Source({2027: [(date(2027, 1, 1), "1월1일")]}), repo).sync()
    assert await repo.list_between(date(2028, 1, 1), date(2028, 12, 31)) == []
    sync = await repo.get_sync(2028)
    assert sync is not None
    assert sync.holiday_count == 0


async def test_failure_keeps_every_year() -> None:
    repo = InMemoryPublicHolidayRepository(PublicHoliday(date(2027, 3, 1), "삼일절"))
    with pytest.raises(ServiceUnavailableError):
        await service(Source({2027: []}, fail=2028), repo).sync()
    assert await repo.list_between(date(2027, 1, 1), date(2027, 12, 31)) == [
        PublicHoliday(date(2027, 3, 1), "삼일절")
    ]
    assert await repo.get_sync(2027) is None

"""기수 멘토링 설정·금지 시간대·추가 휴일 저장과 DB 제약."""

from datetime import UTC, date, datetime, time
from typing import Any

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
    PublicHoliday,
    PublicHolidaySync,
)
from app.contexts.mentoring.infrastructure.models import (
    CohortMentoringBlockTimeModel,
    CohortMentoringSettingsModel,
    PublicHolidayModel,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringBlockTimeRepository,
    TortoiseMentoringHolidayRepository,
    TortoisePublicHolidayRepository,
)
from tests.factories.academy import create_cohort

pytestmark = pytest.mark.integration

blocks = TortoiseMentoringBlockTimeRepository()


async def test_settings_round_trip_and_one_per_cohort() -> None:
    cohort = await create_cohort()
    repo = TortoiseCohortMentoringSettingsRepository()
    await repo.add(CohortMentoringSettings(cohort_id=cohort.id, allow_1_on_1=True))
    loaded = await repo.get_by_cohort(cohort.id)
    assert loaded is not None
    assert (loaded.allow_1_on_1, loaded.min_lead_hours, loaded.allowed_duration) == (True, 24, 30)
    with pytest.raises(IntegrityError):
        await repo.add(CohortMentoringSettings(cohort_id=cohort.id, allow_1_on_1=True))


@pytest.mark.parametrize(
    "values",
    [
        {},  # 팀·1:1 모두 비허용
        {"allow_1_on_1": True, "allowed_duration": 45},
        {"allow_1_on_1": True, "min_lead_hours": 48},
        {"allow_1_on_1": True, "max_pending_requests": 4},
        {"allow_1_on_1": True, "default_1on1_minutes": 90},
    ],
)
async def test_settings_db_checks(values: dict[str, Any]) -> None:
    cohort = await create_cohort()
    with pytest.raises(IntegrityError):
        await CohortMentoringSettingsModel.create(cohort_id=cohort.id, **values)


async def test_block_time_round_trip_keeps_naive_time() -> None:
    cohort = await create_cohort()
    block = MentoringBlockTime(
        cohort_id=cohort.id,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 30),
        start_time=time(9, 0),
        end_time=time(18, 0),
        reason="수업 시간",
    )
    await blocks.add(block)
    loaded = await blocks.get(block.id)
    assert loaded is not None
    assert (loaded.start_time, loaded.end_time) == (time(9, 0), time(18, 0))
    assert loaded.start_time.tzinfo is None


async def test_overlapping_block_times_are_excluded_in_db() -> None:
    cohort = await create_cohort()

    async def create(start: date, end: date, t1: time, t2: time) -> None:
        await CohortMentoringBlockTimeModel.create(
            cohort_id=cohort.id, period_start=start, period_end=end, start_time=t1, end_time=t2
        )

    await create(date(2026, 11, 1), date(2026, 11, 30), time(9), time(12))
    await create(date(2026, 11, 1), date(2026, 11, 30), time(12), time(18))  # 시간대가 맞닿음
    await create(date(2026, 12, 1), date(2026, 12, 31), time(9), time(12))  # 기간이 다름
    with pytest.raises(IntegrityError):
        await create(date(2026, 11, 30), date(2026, 12, 5), time(11), time(13))
    other = await create_cohort()
    await CohortMentoringBlockTimeModel.create(  # 다른 기수는 겹쳐도 된다
        cohort_id=other.id,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 30),
        start_time=time(9),
        end_time=time(12),
    )
    assert [b.start_time for b in await blocks.list_by_cohort(cohort.id)] == [
        time(9),
        time(12),
        time(9),
    ]


async def test_holidays() -> None:
    repo = TortoiseMentoringHolidayRepository()
    await repo.add(MentoringHoliday(holiday_date=date(2026, 11, 20), name="학원 휴무"))
    assert (await repo.get_by_date(date(2026, 11, 20))) is not None
    assert [h.name for h in await repo.list_between(date(2026, 11, 1), date(2026, 11, 30))] == [
        "학원 휴무"
    ]
    with pytest.raises(IntegrityError):
        await repo.add(MentoringHoliday(holiday_date=date(2026, 11, 20), name="중복"))
    _, rows = await connections.get("default").execute_query(
        'SELECT "created_at" FROM "mentoring_holidays"'
    )
    assert rows[0]["created_at"] is not None


async def test_public_holidays_replace_year() -> None:
    repo = TortoisePublicHolidayRepository()
    at = datetime(2026, 11, 25, 18, 0, tzinfo=UTC)
    await repo.replace_year(
        2026,
        [
            PublicHoliday(date(2026, 5, 5), "어린이날"),
            PublicHoliday(date(2026, 5, 5), "부처님오신날"),
        ],
        at,
    )
    await repo.replace_year(2027, [PublicHoliday(date(2027, 1, 1), "1월1일")], at)
    later = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
    await repo.replace_year(2026, [PublicHoliday(date(2026, 9, 25), "추석")], later)

    found = await repo.list_between(date(2026, 1, 1), date(2027, 12, 31))
    assert [(h.holiday_date, h.name) for h in found] == [
        (date(2026, 9, 25), "추석"),
        (date(2027, 1, 1), "1월1일"),
    ]
    assert await repo.get_sync(2026) == PublicHolidaySync(2026, later, 1)
    assert await repo.get_sync(2025) is None

    await repo.replace_year(2026, [], later)  # 0건이면 그해를 비운다
    assert await repo.list_between(date(2026, 1, 1), date(2026, 12, 31)) == []
    with pytest.raises(IntegrityError):
        await PublicHolidayModel.bulk_create(
            [
                PublicHolidayModel(holiday_date=date(2026, 1, 1), name="1월1일"),
                PublicHolidayModel(holiday_date=date(2026, 1, 1), name="1월1일"),
            ]
        )

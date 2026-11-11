"""멘토 불가 시간·기수 운영시간·신청 받기 저장과 DB 제약 (A37)."""

from datetime import date, datetime

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.contexts.mentoring.domain.settings import CohortMentoringSettings, OperatingHours
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentorUnavailablePeriodRepository,
)
from app.shared.time import KST
from tests.factories.academy import create_cohort
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

periods = TortoiseMentorUnavailablePeriodRepository()


async def _update(table: str, sql: str, row_id: object) -> None:
    await connections.get("default").execute_query(
        f"UPDATE {table} SET {sql} WHERE id = $1", [str(row_id)]
    )


async def test_weekly_period_round_trip_and_checks() -> None:
    mentor = await create_mentor()
    work = MentorUnavailablePeriod(
        mentor_id=mentor.id,
        repeat=UnavailableRepeat.WEEKLY,
        weekdays=frozenset({1, 2, 3, 4, 5}),
        starts_at=datetime(2026, 11, 16, 9, tzinfo=KST),
        ends_at=datetime(2026, 11, 16, 18, tzinfo=KST),
        repeat_until=date(2027, 2, 28),
        category="근무",
    )
    await periods.add(work)
    once = MentorUnavailablePeriod.for_dates(
        mentor_id=mentor.id, start_date=date(2026, 11, 16), end_date=date(2026, 11, 16)
    )
    await periods.add(once)  # 겹쳐도 된다

    loaded = await periods.get(work.id)
    assert loaded is not None
    assert loaded.weekdays == frozenset({1, 2, 3, 4, 5})
    assert (loaded.repeat, loaded.category, loaded.repeat_until) == (
        UnavailableRepeat.WEEKLY,
        "근무",
        date(2027, 2, 28),
    )
    assert loaded.updated_at is not None
    assert [p.id for p in await periods.list_by_mentor(mentor.id)] == [once.id, work.id]

    for sql in (
        "weekdays_mask = 0",  # 매주인데 요일 없음
        "weekdays_mask = 128",
        "ends_at = starts_at + interval '25 hours'",  # 반복 회차 24시간 초과
        "starts_at = starts_at + interval '10 minutes'",  # 30분 경계
        "repeat = 'MONTHLY'",
    ):
        with pytest.raises(IntegrityError):
            await _update("mentor_unavailable_periods", sql, work.id)
    for sql in ("repeat_until = '2026-12-01'", "weekdays_mask = 1", "ends_at = starts_at"):
        with pytest.raises(IntegrityError):
            await _update("mentor_unavailable_periods", sql, once.id)


async def test_operating_hours_and_accepting_switch() -> None:
    repo = TortoiseCohortMentoringSettingsRepository()
    cohort = await create_cohort()
    settings = CohortMentoringSettings(
        cohort_id=cohort.id,
        allow_1_on_1=True,
        weekend_hours=OperatingHours.of("13:00", "24:00"),
    )
    await repo.add(settings)
    loaded = await repo.get_by_cohort(cohort.id)
    assert loaded is not None
    assert loaded.weekday_hours == OperatingHours(start_minute=600, end_minute=1140)
    assert loaded.weekend_hours == OperatingHours(start_minute=780, end_minute=1440)
    await repo.save(loaded.changed({"weekday_hours": None}))
    closed = await repo.get_by_cohort(cohort.id)
    assert closed is not None
    assert closed.weekday_hours is None

    for sql in (
        "weekday_open_minute = 600",  # 끝 없이 시작만
        "weekend_open_minute = 790",
        "weekend_close_minute = 1470",
        "weekend_open_minute = 1440",
    ):
        with pytest.raises(IntegrityError):
            await _update("cohort_mentoring_settings", sql, settings.id)

    mentor = await create_mentor()
    assert not mentor.accepting_requests
    mentor.set_accepting(True)
    await TortoiseMentorRepository().save(mentor)
    reloaded = await TortoiseMentorRepository().get(mentor.id)
    assert reloaded is not None
    assert reloaded.accepting_requests

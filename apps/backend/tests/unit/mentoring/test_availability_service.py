"""신청 가능 시간 조회 서비스: 권한·기간·배정·설정·신청 받기 (A37)."""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.availability_service import (
    AvailableTimesService,
    NoBusySchedule,
)
from app.contexts.mentoring.application.calendar import BusinessCalendar
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.availability import Interval
from app.contexts.mentoring.domain.settings import CohortMentoringSettings, MentoringHoliday
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryBlockTimeRepository,
    InMemoryCohortMentorRepository,
    InMemoryPublicHolidayRepository,
    InMemorySettingsRepository,
    InMemoryUnavailablePeriodRepository,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 0, 0, tzinfo=UTC)  # 2026-11-11(수) 09:00 KST
MON = date(2026, 11, 16)


class Holidays:
    async def add(self, holiday: MentoringHoliday) -> None: ...
    async def get(self, holiday_id: uuid.UUID) -> MentoringHoliday | None:
        return None

    async def get_by_date(self, day: date) -> MentoringHoliday | None:
        return None

    async def delete(self, holiday_id: uuid.UUID) -> None: ...
    async def list_between(self, start: date, end: date) -> list[MentoringHoliday]:
        return []


class Enrollments:
    def __init__(self) -> None:
        self.enrolled: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def is_enrolled(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> bool:
        return (user_id, cohort_id) in self.enrolled


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.mentor = Mentor(user_id=new_id(), accepting_requests=True)
        self.mentors = InMemoryMentorRepository(self.mentor)
        self.assignments = InMemoryCohortMentorRepository(
            CohortMentor(
                cohort_id=self.cohort_id,
                mentor_id=self.mentor.id,
                start_date=date(2026, 11, 1),
                contract_id=new_id(),
            )
        )
        self.settings = InMemorySettingsRepository(
            CohortMentoringSettings(cohort_id=self.cohort_id, allow_1_on_1=True)
        )
        self.enrollments = Enrollments()
        self.student = new_id()
        self.enrollments.enrolled.add((self.student, self.cohort_id))
        self.service = AvailableTimesService(
            settings=self.settings,
            assignments=self.assignments,
            unavailable_periods=InMemoryUnavailablePeriodRepository(),
            blocks=InMemoryBlockTimeRepository(),
            calendar=BusinessCalendar(Holidays(), InMemoryPublicHolidayRepository()),
            mentors=MentorQueries(self.mentors),
            enrollments=self.enrollments,
            busy=NoBusySchedule(),
            clock=FixedClock(NOW),
        )

    async def query(
        self,
        start: date = MON,
        end: date = MON,
        *,
        viewer: uuid.UUID | None = None,
        staff: bool = False,
        cohort_id: uuid.UUID | None = None,
    ) -> list[Interval]:
        result = await self.service.query(
            self.mentor.id,
            cohort_id or self.cohort_id,
            start,
            end,
            viewer_id=viewer or self.student,
            viewer_is_staff=staff,
        )
        return result.intervals


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_enrolled_student_sees_operating_hours(h: Harness) -> None:
    (interval,) = await h.query()
    assert interval.start == datetime(2026, 11, 16, 10, tzinfo=KST)
    assert interval.end == datetime(2026, 11, 16, 19, tzinfo=KST)


async def test_viewers(h: Harness) -> None:
    assert await h.query(viewer=h.mentor.user_id)  # 멘토 본인
    assert await h.query(viewer=new_id(), staff=True)  # 운영진
    with pytest.raises(PermissionDeniedError):
        await h.query(viewer=new_id())


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 10), date(2026, 11, 12)),  # 어제부터
        (date(2026, 11, 12), date(2026, 11, 11)),  # 거꾸로
        (date(2026, 11, 11), date(2026, 12, 12)),  # 32일
        (date(2026, 12, 31), date(2027, 1, 11)),  # 60일 넘음
    ],
)
async def test_range_limits(h: Harness, start: date, end: date) -> None:
    with pytest.raises(BusinessRuleViolation) as error:
        await h.query(start, end)
    assert error.value.code == "invalid_time_range"


async def test_range_boundaries_are_allowed(h: Harness) -> None:
    await h.query(date(2026, 11, 11), date(2026, 12, 11))  # 31일
    await h.query(date(2027, 1, 10), date(2027, 1, 10))  # 60일 뒤


async def test_not_assigned_no_settings_or_not_accepting(h: Harness) -> None:
    other_cohort = new_id()
    h.enrollments.enrolled.add((h.student, other_cohort))
    h.settings.items[other_cohort] = CohortMentoringSettings(
        cohort_id=other_cohort, allow_1_on_1=True
    )
    with pytest.raises(NotFoundError) as unassigned:
        await h.query(cohort_id=other_cohort)
    assert unassigned.value.code == "mentor_not_assigned"
    del h.settings.items[h.cohort_id]
    with pytest.raises(NotFoundError) as missing:
        await h.query()
    assert missing.value.code == "mentoring_settings_not_configured"

    h.settings.items[h.cohort_id] = CohortMentoringSettings(
        cohort_id=h.cohort_id, allow_1_on_1=True
    )
    h.mentor.set_accepting(False)
    await h.mentors.save(h.mentor)
    result = await h.service.query(
        h.mentor.id, h.cohort_id, MON, MON, viewer_id=h.student, viewer_is_staff=False
    )
    assert (result.accepting_requests, result.intervals) == (False, [])

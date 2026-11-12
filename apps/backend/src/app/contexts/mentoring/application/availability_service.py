"""신청 가능 시간 조회 (decisions A37).

= 기수 운영시간 − 멘토 불가 시간 − 기수 금지 시간대 − 이미 잡힌 세션 − 신청 마감.
- 볼 수 있는 사람: 그 기수의 수강 중 수강생, 운영진(mentoring.request.read 기수 범위), 멘토 본인.
- 멘토가 그 기수에 활성 배정돼 있어야 하고(아니면 404), 배정 기간 안의 날짜만 연다.
- 신청 받기가 꺼져 있거나 멘토가 비활성이면 빈 목록이다.
- 기수 설정이 없으면 404 `mentoring_settings_not_configured`.
- 조회는 한국 날짜로 한 번에 최대 31일, 오늘부터 60일 뒤까지.
- 이미 잡힌 세션은 P11부터 `BusySchedule` 포트로 뺀다(P9는 없음).
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol

from app.contexts.mentoring.application.calendar import BusinessCalendar
from app.contexts.mentoring.application.schedule_service import MentorLookup
from app.contexts.mentoring.domain.availability import (
    AssignmentRange,
    Interval,
    available_intervals,
)
from app.contexts.mentoring.domain.repositories import (
    CohortMentoringSettingsRepository,
    CohortMentorRepository,
    MentoringBlockTimeRepository,
    MentorUnavailablePeriodRepository,
)
from app.core.clock import Clock
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.time import KST, business_date

MAX_RANGE_DAYS = 31
MAX_AHEAD_DAYS = 60


class EnrollmentLookup(Protocol):
    """academy `StudentQueries`."""

    async def is_enrolled(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> bool: ...


class BusySchedule(Protocol):
    """mentoring 세션 리포지토리 `busy`."""

    async def busy(
        self,
        mentor_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[Interval]:
        """그 멘토의 이미 잡힌 세션 (취소 제외, 변경 중인 신청의 세션 제외)."""
        ...


class NoBusySchedule:
    """잡힌 일정 없음 (단위 테스트용)."""

    async def busy(
        self,
        mentor_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[Interval]:
        return []


@dataclass(frozen=True, slots=True)
class AvailableTimes:
    mentor_id: uuid.UUID
    cohort_id: uuid.UUID
    accepting_requests: bool
    allowed_duration: int
    min_lead_hours: int
    intervals: list[Interval]


class AvailableTimesService:
    def __init__(
        self,
        *,
        settings: CohortMentoringSettingsRepository,
        assignments: CohortMentorRepository,
        unavailable_periods: MentorUnavailablePeriodRepository,
        blocks: MentoringBlockTimeRepository,
        calendar: BusinessCalendar,
        mentors: MentorLookup,
        enrollments: EnrollmentLookup,
        busy: BusySchedule,
        clock: Clock,
    ) -> None:
        self._settings = settings
        self._assignments = assignments
        self._periods = unavailable_periods
        self._blocks = blocks
        self._calendar = calendar
        self._mentors = mentors
        self._enrollments = enrollments
        self._busy = busy
        self._clock = clock

    async def query(
        self,
        mentor_id: uuid.UUID,
        cohort_id: uuid.UUID,
        start: date,
        end: date,
        *,
        viewer_id: uuid.UUID,
        viewer_is_staff: bool,
    ) -> AvailableTimes:
        mentor = await self._mentors.get(mentor_id)
        if mentor is None:
            raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
        if not (
            viewer_is_staff
            or mentor.user_id == viewer_id
            or await self._enrollments.is_enrolled(viewer_id, cohort_id)
        ):
            raise PermissionDeniedError(
                "이 기수의 수강생·운영진·멘토 본인만 볼 수 있습니다.", code="forbidden"
            )
        return await self.times_for(mentor_id, cohort_id, start, end)

    async def times_for(
        self,
        mentor_id: uuid.UUID,
        cohort_id: uuid.UUID,
        start: date,
        end: date,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> AvailableTimes:
        """조회자 확인 없이 계산한다 (신청 검증용, P11). 변경은 기존 신청의 세션을 빼고 본다."""
        now = self._clock.now()
        self._ensure_range(start, end, business_date(now))
        mentor = await self._mentors.get(mentor_id)
        if mentor is None:
            raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
        settings = await self._settings.get_by_cohort(cohort_id)
        if settings is None:
            raise NotFoundError(
                "이 기수의 멘토링 설정이 아직 없습니다.", code="mentoring_settings_not_configured"
            )
        active = [
            a
            for a in await self._assignments.list_by_mentor(mentor_id, include_inactive=False)
            if a.cohort_id == cohort_id
        ]
        if not active:
            raise NotFoundError("이 기수에 배정된 멘토가 아닙니다.", code="mentor_not_assigned")
        result = AvailableTimes(
            mentor_id=mentor_id,
            cohort_id=cohort_id,
            accepting_requests=mentor.accepting_requests and mentor.is_active,
            allowed_duration=settings.allowed_duration,
            min_lead_hours=settings.min_lead_hours,
            intervals=[],
        )
        if not result.accepting_requests:
            return result
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        # 자정을 넘는 회차·이어지는 구간을 위해 앞뒤 하루씩 넉넉히 읽는다
        window_start = datetime.combine(start - timedelta(days=1), time(), KST)
        window_end = datetime.combine(end + timedelta(days=2), time(), KST)
        intervals = available_intervals(
            days=days,
            settings=settings,
            business_days=await self._calendar.business_days(start, end),
            assignments=[AssignmentRange(a.start_date, a.end_date) for a in active],
            unavailable=await self._periods.list_by_mentor(mentor_id),
            blocks=await self._blocks.list_by_cohort(cohort_id),
            busy=await self._busy.busy(
                mentor_id, window_start, window_end, exclude_request_id=exclude_request_id
            ),
            now=now,
        )
        return dataclasses.replace(result, intervals=intervals)

    @staticmethod
    def _ensure_range(start: date, end: date, today: date) -> None:
        if not (
            today <= start <= end
            and (end - start).days < MAX_RANGE_DAYS
            and end <= today + timedelta(days=MAX_AHEAD_DAYS)
        ):
            raise BusinessRuleViolation(
                f"조회 기간은 오늘부터 {MAX_AHEAD_DAYS}일 뒤까지, "
                f"한 번에 최대 {MAX_RANGE_DAYS}일입니다.",
                code="invalid_time_range",
            )

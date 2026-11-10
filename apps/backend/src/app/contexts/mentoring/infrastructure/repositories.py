"""mentoring 리포지토리 구현 (Tortoise)."""

import uuid
from datetime import date

from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
)
from app.contexts.mentoring.infrastructure.models import (
    CohortMentoringBlockTimeModel,
    CohortMentoringSettingsModel,
    MentoringHolidayModel,
)
from app.core.persistence import TortoiseRepository


class TortoiseCohortMentoringSettingsRepository(
    TortoiseRepository[CohortMentoringSettings, CohortMentoringSettingsModel]
):
    model = CohortMentoringSettingsModel
    entity = CohortMentoringSettings
    fields = (
        "cohort_id",
        "allow_team_mentoring",
        "allow_1_on_1",
        "default_1on1_minutes",
        "default_team_minutes",
        "min_lead_hours",
        "allowed_duration",
        "max_pending_requests",
    )

    def to_entity(self, row: CohortMentoringSettingsModel) -> CohortMentoringSettings:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    async def get_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        row = await CohortMentoringSettingsModel.get_or_none(cohort_id=cohort_id)
        return self.to_entity(row) if row else None


class TortoiseMentoringBlockTimeRepository(
    TortoiseRepository[MentoringBlockTime, CohortMentoringBlockTimeModel]
):
    model = CohortMentoringBlockTimeModel
    entity = MentoringBlockTime
    fields = ("cohort_id", "period_start", "period_end", "start_time", "end_time", "reason")

    def to_entity(self, row: CohortMentoringBlockTimeModel) -> MentoringBlockTime:
        # 컬럼은 시간대 없는 TIME(한국 시각 "시:분")이다. Tortoise(use_tz)가 붙이는 UTC를 뗀다
        entity = super().to_entity(row)
        entity.start_time = entity.start_time.replace(tzinfo=None)
        entity.end_time = entity.end_time.replace(tzinfo=None)
        return entity

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringBlockTime]:
        rows = await CohortMentoringBlockTimeModel.filter(cohort_id=cohort_id).order_by(
            "period_start", "start_time", "id"
        )
        return [self.to_entity(row) for row in rows]


class TortoiseMentoringHolidayRepository(
    TortoiseRepository[MentoringHoliday, MentoringHolidayModel]
):
    model = MentoringHolidayModel
    entity = MentoringHoliday
    fields = ("holiday_date", "name")

    async def get_by_date(self, day: date) -> MentoringHoliday | None:
        row = await MentoringHolidayModel.get_or_none(holiday_date=day)
        return self.to_entity(row) if row else None

    async def list_between(self, start: date, end: date) -> list[MentoringHoliday]:
        rows = await MentoringHolidayModel.filter(
            holiday_date__gte=start, holiday_date__lte=end
        ).order_by("holiday_date")
        return [self.to_entity(row) for row in rows]

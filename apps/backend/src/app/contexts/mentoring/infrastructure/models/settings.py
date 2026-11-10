"""기수 멘토링 설정·금지 시간대·추가 휴일 모델 (decisions A34).

check·EXCLUDE·기본값은 마이그레이션 raw SQL로 건다.
"""

from typing import Any

from tortoise import fields, models

from app.shared.ids import new_id


class CohortMentoringSettingsModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    cohort: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    allow_team_mentoring = fields.BooleanField(default=False)
    allow_1_on_1 = fields.BooleanField(default=False)
    default_1on1_minutes = fields.IntField(default=0)
    default_team_minutes = fields.IntField(default=0)
    min_lead_hours = fields.SmallIntField(default=24)
    allowed_duration = fields.SmallIntField(default=30)
    max_pending_requests = fields.SmallIntField(default=1)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cohort_mentoring_settings"


class CohortMentoringBlockTimeModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    period_start = fields.DateField()
    period_end = fields.DateField()
    start_time = fields.TimeField()
    end_time = fields.TimeField()
    reason = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cohort_mentoring_block_times"
        indexes = (("cohort", "period_start"),)


class MentoringHolidayModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    holiday_date = fields.DateField(unique=True)
    name = fields.CharField(max_length=50)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_holidays"

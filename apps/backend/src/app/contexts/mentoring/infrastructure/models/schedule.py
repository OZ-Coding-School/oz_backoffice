"""멘토 불가 시간 모델 (decisions A37). check·기본값은 마이그레이션 raw SQL로 건다."""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import UnavailableRepeat
from app.shared.ids import new_id


class MentorUnavailablePeriodModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    repeat = fields.CharEnumField(UnavailableRepeat, max_length=10, default=UnavailableRepeat.ONCE)
    starts_at = fields.DatetimeField()
    ends_at = fields.DatetimeField()
    weekdays_mask = fields.SmallIntField(default=0)  # 매주 반복 요일 비트 (월=1 … 일=64)
    repeat_until = fields.DateField(null=True)
    category = fields.CharField(max_length=30, null=True)
    reason = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentor_unavailable_periods"
        indexes = (("mentor", "starts_at"),)

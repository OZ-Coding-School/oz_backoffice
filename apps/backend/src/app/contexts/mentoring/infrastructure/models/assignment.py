"""기수 멘토 배정 모델 (decisions A35). check·부분 유니크·기본값은 마이그레이션 raw SQL로 건다."""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.shared.ids import new_id


class CohortMentorModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    start_date = fields.DateField()
    end_date = fields.DateField(null=True)
    cost_settlement_policy = fields.CharEnumField(MentoringSettlementPolicy, max_length=30)
    pay_unit = fields.CharEnumField(PayUnit, max_length=20)
    pay_rate = fields.IntField()
    no_show_pay_amount = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    deactivated_at = fields.DatetimeField(null=True)
    deactivation_reason = fields.CharEnumField(
        CohortMentorDeactivationReason, max_length=30, null=True
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cohort_mentors"
        indexes = (("cohort", "is_active"), ("is_active", "end_date"), ("mentor", "is_active"))

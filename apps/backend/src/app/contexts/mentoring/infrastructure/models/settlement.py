"""정산·정산 명세 모델 (M16·A55). enum·마감 CHECK·기본값은 마이그레이션 raw SQL."""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.shared.ids import new_id


class MentoringSettlementModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    settlement_month = fields.DateField()
    status = fields.CharEnumField(
        MentoringSettlementStatus, max_length=20, default=MentoringSettlementStatus.DRAFT
    )
    session_count = fields.IntField(default=0)
    total_minutes = fields.IntField(default=0)
    total_amount = fields.IntField(default=0)
    closed_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_settlements"
        unique_together = (("mentor", "cohort", "settlement_month"),)
        indexes = (("cohort", "settlement_month"),)


class MentoringSettlementItemModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    session: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.MentoringSessionModel", related_name=False, on_delete=fields.RESTRICT
    )
    settlement: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentoringSettlementModel", related_name=False, on_delete=fields.CASCADE
    )
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    item_type = fields.CharEnumField(SettlementItemType, max_length=20)
    settlement_policy = fields.CharEnumField(MentoringSettlementPolicy, max_length=30)
    billable_minutes = fields.IntField()
    pay_unit = fields.CharEnumField(PayUnit, max_length=20)
    pay_rate = fields.IntField()
    amount = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mentoring_settlement_items"
        indexes = (("settlement",),)

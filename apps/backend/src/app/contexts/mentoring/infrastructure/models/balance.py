"""멘토링 시간 계좌·원장 모델 (decisions M8·M9·M10·A39).

부분 유니크·check·기본값은 마이그레이션 raw SQL로 건다.
원장의 request_id → mentoring_requests FK는 신청 테이블이 생기는 P11에서 건다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType, MentoringPeriodType
from app.shared.ids import new_id


class MentoringBalanceAccountModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    student: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.StudentModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    team: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.MentoringTeamModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    period_type = fields.CharEnumField(MentoringPeriodType, max_length=30)
    valid_from = fields.DateField()
    valid_until = fields.DateField()
    total_minutes = fields.IntField(default=0)
    held_minutes = fields.IntField(default=0)
    used_minutes = fields.IntField(default=0)
    remaining_minutes = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_balance_accounts"


class MentoringBalanceTransactionModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    account: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentoringBalanceAccountModel", related_name=False, on_delete=fields.RESTRICT
    )
    request_id = fields.UUIDField(null=True)
    type = fields.CharEnumField(MentoringBalanceTransactionType, max_length=20)
    amount = fields.IntField()
    after_remaining = fields.IntField()
    after_held = fields.IntField()
    reason = fields.CharField(max_length=100)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mentoring_balance_transactions"
        indexes = (("account", "created_at"),)

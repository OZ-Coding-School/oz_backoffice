"""멘토링 신청 모델 (decisions M1·M3·A42).

check·자기 참조 FK(replaced_request_id)·원장 request_id FK·기본값은 마이그레이션 raw SQL로 건다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.shared.ids import new_id


class MentoringRequestModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    replaced_request_id = fields.UUIDField(null=True, unique=True)  # 자기 참조 FK는 raw SQL
    team: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.MentoringTeamModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    requester: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.StudentModel", related_name=False, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    topic = fields.CharField(max_length=100)
    detail = fields.TextField()
    desired_at_1 = fields.DatetimeField()
    desired_at_2 = fields.DatetimeField(null=True)
    desired_at_3 = fields.DatetimeField(null=True)
    duration = fields.SmallIntField()
    status = fields.CharEnumField(
        MentoringRequestStatus, max_length=20, default=MentoringRequestStatus.PENDING
    )
    rejected_at = fields.DatetimeField(null=True)
    reject_reason = fields.CharField(max_length=300, null=True)
    canceled_at = fields.DatetimeField(null=True)
    cancel_reason = fields.CharField(max_length=300, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_requests"
        indexes = (("mentor", "status"), ("requester", "created_at"), ("team",), ("status",))

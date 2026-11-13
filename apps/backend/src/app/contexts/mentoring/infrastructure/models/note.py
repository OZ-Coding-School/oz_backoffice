"""멘토 내부 메모 모델 (decisions M22·A53). 길이 check·기본값은 마이그레이션 raw SQL."""

from typing import Any

from tortoise import fields, models

from app.shared.ids import new_id


class MentoringSessionNoteModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    session: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.MentoringSessionModel", related_name=False, on_delete=fields.RESTRICT
    )
    body = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_session_notes"

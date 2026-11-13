"""Meet 녹화·전사·요약 파일 모델 (M19·A54). enum CHECK·기본값은 마이그레이션 raw SQL."""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import MentoringArtifactStatus, MentoringArtifactType
from app.shared.ids import new_id


class MentoringArtifactModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    session: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentoringSessionModel", related_name=False, on_delete=fields.RESTRICT
    )
    drive_file_id = fields.CharField(max_length=255)
    artifact_type = fields.CharEnumField(MentoringArtifactType, max_length=20)
    file_name = fields.CharField(max_length=255, null=True)
    mime_type = fields.CharField(max_length=100, null=True)
    file_size = fields.BigIntField(null=True)
    status = fields.CharEnumField(
        MentoringArtifactStatus, max_length=20, default=MentoringArtifactStatus.PENDING
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_artifacts"
        unique_together = (("session", "drive_file_id"),)
        indexes = (("status",),)

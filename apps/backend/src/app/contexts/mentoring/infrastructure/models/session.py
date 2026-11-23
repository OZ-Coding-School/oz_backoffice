"""멘토링 세션 모델 (decisions M3·A42·A43).

멘토 일정 겹침 EXCLUDE·check·기본값은 마이그레이션 raw SQL로 건다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import MentoringSessionStatus, RecordingStatus
from app.shared.ids import new_id


class MentoringSessionModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    request: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.MentoringRequestModel", related_name=False, on_delete=fields.RESTRICT
    )
    status = fields.CharEnumField(
        MentoringSessionStatus, max_length=20, default=MentoringSessionStatus.SCHEDULED
    )
    starts_at = fields.DatetimeField()
    ends_at = fields.DatetimeField()
    title = fields.CharField(max_length=100)
    topic = fields.CharField(max_length=100)
    body = fields.TextField(null=True)
    record_duration_minutes = fields.SmallIntField(null=True)
    uncharged_overtime_minutes = fields.SmallIntField(null=True)
    recorded_at = fields.DatetimeField(null=True)
    google_space_name = fields.CharField(max_length=255, null=True, unique=True)
    google_meet_url = fields.CharField(max_length=255, null=True)
    google_conference_record_name = fields.CharField(max_length=255, null=True)
    actual_started_at = fields.DatetimeField(null=True)
    actual_ended_at = fields.DatetimeField(null=True)
    recording_status = fields.CharEnumField(
        RecordingStatus, max_length=20, default=RecordingStatus.PENDING
    )
    recording_started_at = fields.DatetimeField(null=True)
    recording_ended_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_sessions"
        indexes = (("mentor", "starts_at"), ("recording_status", "ends_at"))

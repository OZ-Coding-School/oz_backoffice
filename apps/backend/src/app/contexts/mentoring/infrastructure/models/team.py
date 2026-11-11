"""멘토링 팀 모델 (decisions M11·A39).

유니크·복합 FK·기본값·check는 마이그레이션 raw SQL로 건다.
팀원 → 팀 FK는 (team_id, period_type) 복합 FK로 같은 유형임을 보장한다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.shared.ids import new_id


class MentoringTeamModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    team_number = fields.SmallIntField()
    period_type = fields.CharEnumField(MentoringPeriodType, max_length=30)
    name = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_teams"
        unique_together = (("cohort", "period_type", "team_number"),)
        indexes = (("mentor",),)


class MentoringTeamMemberModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    student: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.StudentModel", related_name=False, on_delete=fields.RESTRICT
    )
    # 복합 FK (team_id, period_type) → mentoring_teams(id, period_type)는 raw SQL로 건다
    team_id = fields.UUIDField()
    period_type = fields.CharEnumField(MentoringPeriodType, max_length=30)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mentoring_team_members"
        unique_together = (("team_id", "student"), ("student", "period_type"))

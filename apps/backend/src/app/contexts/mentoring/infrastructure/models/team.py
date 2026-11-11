"""멘토링 팀 모델 (decisions M11·A39).

유니크·FK·기본값·check는 마이그레이션 raw SQL로 건다 (유형 구분 없음, A41).
"""

from typing import Any

from tortoise import fields, models

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
    name = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentoring_teams"
        unique_together = (("cohort", "team_number"),)
        indexes = (("mentor",),)


class MentoringTeamMemberModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    student: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.StudentModel", related_name=False, on_delete=fields.RESTRICT
    )
    # 팀 FK(ON DELETE CASCADE)는 raw SQL로 건다
    team_id = fields.UUIDField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mentoring_team_members"
        unique_together = (("team_id", "student"), ("student",))  # 수강 등록당 한 팀

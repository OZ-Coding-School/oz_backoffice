"""멘토링 채팅 모델 (decisions M23·A57).

- 채팅방의 부분 유니크((수강 등록, 멘토)·(팀, 멘토))와 1:1/팀 check, 기본값은 마이그레이션 raw SQL.
- 메시지 삭제 check(지웠으면 본문 없음, 남아 있으면 본문 있음)도 raw SQL.
- 읽음 위치 `mentoring_chat_reads`는 복합 PK (thread_id, user_id)라 Tortoise 모델 없이 마이그레이션
  raw SQL로 만들고 리포지토리가 SQL로 다룬다(Tortoise는 복합 PK를 지원하지 않는다).
"""

from typing import Any

from tortoise import fields, models

from app.shared.ids import new_id


class MentoringChatThreadModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    student: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.StudentModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    team: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.MentoringTeamModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentorModel", related_name=False, on_delete=fields.RESTRICT
    )
    last_message_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "mentoring_chat_threads"
        indexes = (
            ("mentor", "last_message_at"),
            ("student", "last_message_at"),
            ("team", "last_message_at"),
        )


class MentoringChatMessageModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)  # uuid7: 커서·정렬 기준
    thread: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.MentoringChatThreadModel", related_name=False, on_delete=fields.RESTRICT
    )
    sender: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    body = fields.TextField(null=True)
    created_at = fields.DatetimeField()
    deleted_at = fields.DatetimeField(null=True)

    class Meta:
        table = "mentoring_chat_messages"
        indexes = (("thread", "id"),)

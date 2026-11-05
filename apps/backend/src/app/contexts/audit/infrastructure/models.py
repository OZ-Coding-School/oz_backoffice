"""audit 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: docs/database_schema_v2.dbml — audit_logs
"""

from typing import Any

from tortoise import fields, models

from app.shared.ids import new_id


class AuditLogModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    # 회원이 삭제(soft delete)되어도 로그는 남긴다. 물리 삭제 시에는 actor만 비운다
    actor_user: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, null=True, on_delete=fields.SET_NULL
    )
    action = fields.CharField(max_length=100)
    target_type = fields.CharField(max_length=50)
    target_id = fields.UUIDField(null=True)
    before = fields.JSONField[dict[str, Any] | None](null=True)
    after = fields.JSONField[dict[str, Any] | None](null=True)
    ip = fields.CharField(max_length=45, null=True)
    created_at = fields.DatetimeField()

    class Meta:
        table = "audit_logs"
        indexes = (("target_type", "target_id", "created_at"), ("actor_user", "created_at"))

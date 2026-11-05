"""identity 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: docs/database_schema_v2.dbml — users, oauth_accounts
DBML check 제약은 Tortoise로 표현할 수 없어 마이그레이션에 raw SQL로 추가한다.
"""

from tortoise import fields, models

from app.contexts.identity.domain.enums import SocialLoginProvider, UserApprovalStatus
from app.shared.ids import new_id


class UserModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    email = fields.CharField(max_length=255, unique=True)
    hashed_password = fields.CharField(max_length=255, null=True)
    name = fields.CharField(max_length=50)
    phone_number = fields.CharField(max_length=11, null=True, unique=True)
    birth_date = fields.DateField(null=True)
    approval_status = fields.CharEnumField(
        UserApprovalStatus, max_length=20, default=UserApprovalStatus.PENDING
    )
    approved_at = fields.DatetimeField(null=True)
    email_verified_at = fields.DatetimeField(null=True)
    phone_verified_at = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=False)
    last_login_at = fields.DatetimeField(null=True)
    deleted_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class OAuthAccountModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    user: fields.ForeignKeyRelation[UserModel] = fields.ForeignKeyField(
        "models.UserModel", related_name="oauth_accounts", on_delete=fields.CASCADE
    )
    provider = fields.CharEnumField(SocialLoginProvider, max_length=20)
    oauth_provider_id = fields.CharField(max_length=255)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "oauth_accounts"
        unique_together = (("provider", "oauth_provider_id"), ("user", "provider"))

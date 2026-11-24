"""access 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: roles, permissions, role_permissions, user_roles
- role_permissions는 M2M through 테이블이다.
  복합 PK (role_id, permission_id)는 마이그레이션 raw SQL로 건다.
- user_roles (user_id, role_id, scope_type, scope_id) 유일 제약은
  GLOBAL(scope_id NULL)끼리도 막아야 하므로 `UNIQUE NULLS NOT DISTINCT` 인덱스로 둔다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.access.domain.enums import RoleScopeKind, RoleScopeType
from app.shared.ids import new_id


class PermissionModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    code = fields.CharField(max_length=100, unique=True)
    description = fields.TextField(null=True)

    class Meta:
        table = "permissions"


class RoleModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    # 새 역할의 허용 범위 (A84). 기본 역할은 null이고 코드 정의(catalog.py)를 따른다
    scope_kind = fields.CharEnumField(RoleScopeKind, max_length=20, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    permissions: fields.ManyToManyRelation[PermissionModel] = fields.ManyToManyField(
        "models.PermissionModel",
        through="role_permissions",
        related_name="roles",
        forward_key="permission_id",
        backward_key="role_id",
    )

    class Meta:
        table = "roles"


class UserRoleModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    role: fields.ForeignKeyRelation[RoleModel] = fields.ForeignKeyField(
        "models.RoleModel", related_name="user_roles", on_delete=fields.RESTRICT
    )
    user: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    scope_type = fields.CharEnumField(RoleScopeType, max_length=20)
    scope_id = fields.UUIDField(null=True)
    expires_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_roles"
        indexes = (("scope_type", "scope_id"),)

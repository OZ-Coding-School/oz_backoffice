"""educator 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: mentors, instructors, educator_contracts, contract_files.
check 제약·enum 값·DB 기본값은 마이그레이션 raw SQL로 추가한다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.educator.domain.enums import (
    ContractStatus,
    DisplayNamePreference,
    EducatorType,
)
from app.shared.ids import new_id


class MentorModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    user: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    nickname = fields.CharField(max_length=30, null=True)
    display_name_preference = fields.CharEnumField(
        DisplayNamePreference, max_length=10, default=DisplayNamePreference.NAME
    )
    headline = fields.CharField(max_length=100, null=True)
    introduction = fields.TextField(null=True)
    expertise = fields.CharField(max_length=200, null=True)
    profile_image_key = fields.CharField(max_length=1024, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentors"


class InstructorModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    user: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    nickname = fields.CharField(max_length=30, null=True)
    display_name_preference = fields.CharEnumField(
        DisplayNamePreference, max_length=10, default=DisplayNamePreference.NAME
    )
    headline = fields.CharField(max_length=100, null=True)
    introduction = fields.TextField(null=True)
    expertise = fields.CharField(max_length=200, null=True)
    profile_image_key = fields.CharField(max_length=1024, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "instructors"


class ContractFileModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    file_name = fields.CharField(max_length=100)
    file_ext = fields.CharField(max_length=10)
    file_size = fields.BigIntField()
    storage_key = fields.CharField(max_length=1024, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    deleted_at = fields.DatetimeField(null=True)

    class Meta:
        table = "contract_files"


class EducatorContractModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    manager_employee: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.EmployeeModel", related_name=False, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyNullableRelation[MentorModel] = fields.ForeignKeyField(
        "models.MentorModel", related_name="contracts", null=True, on_delete=fields.RESTRICT
    )
    instructor: fields.ForeignKeyNullableRelation[InstructorModel] = fields.ForeignKeyField(
        "models.InstructorModel", related_name="contracts", null=True, on_delete=fields.RESTRICT
    )
    # DRAFT는 계약서 없이 만들 수 있다 (A23)
    contract_file: fields.OneToOneNullableRelation[ContractFileModel] = fields.OneToOneField(
        "models.ContractFileModel", related_name="contract", null=True, on_delete=fields.RESTRICT
    )
    educator_type = fields.CharEnumField(EducatorType, max_length=20)
    contractor_name = fields.CharField(max_length=50)
    contractor_email = fields.CharField(max_length=255, null=True)
    contractor_phone = fields.CharField(max_length=11)
    title = fields.CharField(max_length=100)
    start_date = fields.DateField()
    end_date = fields.DateField()
    status = fields.CharEnumField(ContractStatus, max_length=20, default=ContractStatus.DRAFT)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "educator_contracts"
        indexes = (("contractor_name", "contractor_phone"), ("mentor",), ("instructor",))

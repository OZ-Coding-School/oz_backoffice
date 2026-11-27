"""educator 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: mentors, instructors, educator_contracts, contract_amendments, contract_files.
check 제약·enum 값·DB 기본값은 마이그레이션 raw SQL로 추가한다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.educator.domain.enums import (
    ContractStatus,
    ContractType,
    DisplayNamePreference,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    TerminationReason,
    VatType,
)
from app.shared.ids import new_id


class MentorModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    # 가입 전 멘토(A104)는 계정 없이 연락처만 둔다 (check_mentor_account_or_contact)
    user: fields.OneToOneNullableRelation[Any] = fields.OneToOneField(
        "models.UserModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    contact_name = fields.CharField(max_length=50, null=True)
    contact_phone = fields.CharField(max_length=11, null=True)
    nickname = fields.CharField(max_length=30, null=True)
    display_name_preference = fields.CharEnumField(
        DisplayNamePreference, max_length=10, default=DisplayNamePreference.NAME
    )
    headline = fields.CharField(max_length=100, null=True)
    introduction = fields.TextField(null=True)
    expertise = fields.CharField(max_length=200, null=True)
    profile_image_key = fields.CharField(max_length=1024, null=True)
    is_active = fields.BooleanField(default=True)
    accepting_requests = fields.BooleanField(default=False)  # 신청 받기 (A37)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "mentors"
        indexes = (("contact_name", "contact_phone"),)


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
    """계약 (A109). 종류·과정·기수·상태·금액·당사자·취소/해지."""

    id = fields.UUIDField(primary_key=True, default=new_id)
    manager_employee: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.EmployeeModel", related_name=False, on_delete=fields.RESTRICT
    )
    bootcamp: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.BootcampModel", related_name=False, on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    mentor: fields.ForeignKeyNullableRelation[MentorModel] = fields.ForeignKeyField(
        "models.MentorModel", related_name="contracts", null=True, on_delete=fields.RESTRICT
    )
    instructor: fields.ForeignKeyNullableRelation[InstructorModel] = fields.ForeignKeyField(
        "models.InstructorModel", related_name="contracts", null=True, on_delete=fields.RESTRICT
    )
    # IN_PROGRESS부터 필수 (A109⑥, check_contract_file_required)
    contract_file: fields.OneToOneNullableRelation[ContractFileModel] = fields.OneToOneField(
        "models.ContractFileModel", related_name="contract", null=True, on_delete=fields.RESTRICT
    )
    # 서명된 계약서, SIGNED부터 필수 (A113, check_contract_signed_file_required)
    signed_contract_file: fields.OneToOneNullableRelation[ContractFileModel] = fields.OneToOneField(
        "models.ContractFileModel",
        related_name="signed_contract",
        null=True,
        on_delete=fields.RESTRICT,
    )
    contract_type = fields.CharEnumField(ContractType, max_length=20)
    title = fields.CharField(max_length=100)
    contractor_name = fields.CharField(max_length=50)
    contractor_email = fields.CharField(max_length=255, null=True)
    contractor_phone = fields.CharField(max_length=11, null=True)
    business_registration_number = fields.CharField(max_length=10, null=True)
    contact_person_name = fields.CharField(max_length=50, null=True)
    start_date = fields.DateField(null=True)
    end_date = fields.DateField(null=True)
    settlement_type = fields.CharEnumField(SettlementType, max_length=20)
    total_amount = fields.BigIntField(null=True)
    unit_price = fields.BigIntField(null=True)
    price_unit = fields.CharEnumField(PriceUnit, max_length=20, null=True)
    vat_type = fields.CharEnumField(VatType, max_length=20)
    amount_note = fields.CharField(max_length=500, null=True)
    no_show_pay_amount = fields.BigIntField(null=True)
    mentoring_time_basis = fields.CharEnumField(MentoringTimeBasis, max_length=20, null=True)
    status = fields.CharEnumField(ContractStatus, max_length=20, default=ContractStatus.DRAFT)
    cancel_reason = fields.CharField(max_length=500, null=True)
    canceled_on = fields.DateField(null=True)
    termination_reason = fields.CharEnumField(TerminationReason, max_length=40, null=True)
    termination_detail = fields.CharField(max_length=500, null=True)
    terminated_on = fields.DateField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "educator_contracts"
        indexes = (
            ("contractor_name", "contractor_phone"),
            ("mentor",),
            ("instructor",),
            ("bootcamp", "cohort"),
            ("status", "start_date"),
        )


class ContractAmendmentModel(models.Model):
    """서명 후 변경 계약 이력 (A109⑨)."""

    id = fields.UUIDField(primary_key=True, default=new_id)
    contract: fields.ForeignKeyRelation[EducatorContractModel] = fields.ForeignKeyField(
        "models.EducatorContractModel", related_name="amendments", on_delete=fields.RESTRICT
    )
    amended_on = fields.DateField()
    reason = fields.CharField(max_length=500)
    before = fields.JSONField[dict[str, Any]]()
    after = fields.JSONField[dict[str, Any]]()
    contract_file: fields.OneToOneNullableRelation[ContractFileModel] = fields.OneToOneField(
        "models.ContractFileModel", related_name="amendment", null=True, on_delete=fields.RESTRICT
    )
    created_by_user: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "contract_amendments"
        indexes = (("contract", "created_at"),)

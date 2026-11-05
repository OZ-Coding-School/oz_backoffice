"""organization 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: departments, employee_positions, employees, bootcamp_staffs, cohort_staffs,
employee_registrations, employee_registration_assignments
`departments (parent_id, name)` 유일 제약은 최상위 부서(parent_id NULL)끼리도 막아야 하므로
Tortoise의 unique_together 대신 마이그레이션에 `UNIQUE NULLS NOT DISTINCT` 인덱스로 둔다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.shared.ids import new_id


class DepartmentModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    # 자기 참조 FK는 aerich가 "cyclic fk references"로 마이그레이션 생성을 거부한다.
    # Tortoise에는 일반 컬럼으로 두고, FK 제약(ON DELETE RESTRICT)은 마이그레이션 raw SQL로 건다.
    parent_id = fields.UUIDField(null=True)
    name = fields.CharField(max_length=20)
    description = fields.CharField(max_length=500)
    rules = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "departments"


class EmployeePositionModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    name = fields.CharField(max_length=20, unique=True)
    priority = fields.SmallIntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "employee_positions"


class EmployeeModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    department: fields.ForeignKeyRelation[DepartmentModel] = fields.ForeignKeyField(
        "models.DepartmentModel", related_name="employees", on_delete=fields.RESTRICT
    )
    position: fields.ForeignKeyRelation[EmployeePositionModel] = fields.ForeignKeyField(
        "models.EmployeePositionModel", related_name="employees", on_delete=fields.RESTRICT
    )
    user: fields.OneToOneRelation[Any] = fields.OneToOneField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    employment_type = fields.CharEnumField(EmploymentType, max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "employees"


class BootcampStaffModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    employee: fields.ForeignKeyRelation[EmployeeModel] = fields.ForeignKeyField(
        "models.EmployeeModel", related_name="bootcamp_staffs", on_delete=fields.RESTRICT
    )
    bootcamp: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.BootcampModel", related_name=False, on_delete=fields.RESTRICT
    )
    role = fields.CharEnumField(StaffRole, max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "bootcamp_staffs"
        unique_together = (("employee", "bootcamp", "role"),)
        indexes = (("bootcamp",),)


class CohortStaffModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    employee: fields.ForeignKeyRelation[EmployeeModel] = fields.ForeignKeyField(
        "models.EmployeeModel", related_name="cohort_staffs", on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, on_delete=fields.RESTRICT
    )
    role = fields.CharEnumField(StaffRole, max_length=20)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "cohort_staffs"
        unique_together = (("employee", "cohort", "role"),)
        indexes = (("cohort",),)


# 운영진 가입 신청 (decisions A11). 회원당 PENDING 신청 하나는 마이그레이션 부분 유니크로 막는다.
class EmployeeRegistrationModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    user: fields.ForeignKeyRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, on_delete=fields.RESTRICT
    )
    department: fields.ForeignKeyRelation[DepartmentModel] = fields.ForeignKeyField(
        "models.DepartmentModel", related_name=False, on_delete=fields.RESTRICT
    )
    position: fields.ForeignKeyRelation[EmployeePositionModel] = fields.ForeignKeyField(
        "models.EmployeePositionModel", related_name=False, on_delete=fields.RESTRICT
    )
    employment_type = fields.CharEnumField(EmploymentType, max_length=20)
    status = fields.CharEnumField(
        EmployeeRegistrationStatus, max_length=20, default=EmployeeRegistrationStatus.PENDING
    )
    reviewed_at = fields.DatetimeField(null=True)
    reject_reason = fields.CharField(max_length=300, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    assignments: fields.ReverseRelation["EmployeeRegistrationAssignmentModel"]

    class Meta:
        table = "employee_registrations"
        indexes = (("user", "created_at"), ("status", "created_at"))


class EmployeeRegistrationAssignmentModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    registration: fields.ForeignKeyRelation[EmployeeRegistrationModel] = fields.ForeignKeyField(
        "models.EmployeeRegistrationModel", related_name="assignments", on_delete=fields.CASCADE
    )
    role = fields.CharEnumField(StaffRole, max_length=20)
    bootcamp: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.BootcampModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "employee_registration_assignments"

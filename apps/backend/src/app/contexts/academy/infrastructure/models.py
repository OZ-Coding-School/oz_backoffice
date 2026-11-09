"""academy 컨텍스트 Tortoise 모델 (단일 app `models`).

DBML: hrd_net_bootcamps, hrd_net_bootcamp_cohorts, bootcamps, cohorts, students,
roster_sync_runs. check 제약·enum 값·DB 기본값은 마이그레이션 raw SQL로 추가한다.
마스터 데이터 FK는 이력 보존을 위해 RESTRICT(삭제 대신 비활성·보관)로 둔다.
"""

from typing import Any

from tortoise import fields, models

from app.contexts.academy.domain.enums import (
    CohortStatus,
    DayNightSeType,
    EnrollmentStatus,
    HRDNetTrainType,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
    WeekendSeType,
)
from app.shared.ids import new_id


class HrdNetBootcampModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    name = fields.CharField(max_length=100)
    hrd_net_id = fields.CharField(max_length=100, null=True, unique=True)
    train_type = fields.CharEnumField(HRDNetTrainType, max_length=10, null=True)
    ncs1_se = fields.CharField(max_length=10, null=True)
    ncs2_se = fields.CharField(max_length=10, null=True)
    ncs3_se = fields.CharField(max_length=10, null=True)
    weekend_se = fields.CharEnumField(WeekendSeType, max_length=10, default=WeekendSeType.WEEKDAY)
    day_night_se = fields.CharEnumField(DayNightSeType, max_length=10, default=DayNightSeType.DAY)
    total_train_fee = fields.IntField(null=True)
    train_fee_per_hour = fields.IntField(null=True)
    total_train_hours = fields.SmallIntField(null=True)
    total_train_days = fields.SmallIntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "hrd_net_bootcamps"


class HrdNetBootcampCohortModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    hrd_net_bootcamp: fields.ForeignKeyRelation[HrdNetBootcampModel] = fields.ForeignKeyField(
        "models.HrdNetBootcampModel", related_name="cohorts", on_delete=fields.RESTRICT
    )
    cohort_number = fields.SmallIntField()
    train_start_date = fields.DateField(null=True)
    train_end_date = fields.DateField(null=True)
    self_pay_amount = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "hrd_net_bootcamp_cohorts"
        unique_together = (("hrd_net_bootcamp", "cohort_number"),)


class BootcampModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    hrd_net_bootcamp: fields.ForeignKeyRelation[HrdNetBootcampModel] = fields.ForeignKeyField(
        "models.HrdNetBootcampModel", related_name="bootcamps", on_delete=fields.RESTRICT
    )
    name = fields.CharField(max_length=50, unique=True)
    code = fields.CharField(max_length=20, unique=True)
    is_active = fields.BooleanField(default=True)
    airtable_cohort_prefix = fields.CharField(max_length=50, null=True, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "bootcamps"
        indexes = (("hrd_net_bootcamp",),)


class CohortModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    hrd_net_cohort: fields.ForeignKeyRelation[HrdNetBootcampCohortModel] = fields.ForeignKeyField(
        "models.HrdNetBootcampCohortModel", related_name="cohorts", on_delete=fields.RESTRICT
    )
    bootcamp: fields.ForeignKeyRelation[BootcampModel] = fields.ForeignKeyField(
        "models.BootcampModel", related_name="cohorts", on_delete=fields.RESTRICT
    )
    cohort_number = fields.SmallIntField()
    start_date = fields.DateField()
    end_date = fields.DateField()
    status = fields.CharEnumField(CohortStatus, max_length=20, default=CohortStatus.PLANNED)
    discord_guild_id = fields.CharField(max_length=32, null=True, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "cohorts"
        unique_together = (("bootcamp", "cohort_number"),)
        indexes = (("hrd_net_cohort",),)


class StudentModel(models.Model):
    """수강 등록 = Airtable 명단 레코드 (decisions A10). 가입 전에는 user가 NULL."""

    id = fields.UUIDField(primary_key=True, default=new_id)
    user: fields.ForeignKeyNullableRelation[Any] = fields.ForeignKeyField(
        "models.UserModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyRelation[CohortModel] = fields.ForeignKeyField(
        "models.CohortModel", related_name="students", on_delete=fields.RESTRICT
    )
    # Airtable이 원천인 필드
    airtable_record_id = fields.CharField(max_length=32, null=True, unique=True)
    name = fields.CharField(max_length=50)
    phone_number = fields.CharField(max_length=11, null=True)
    email = fields.CharField(max_length=255, null=True)
    hrd_net_status = fields.CharEnumField(StudentStatus, max_length=30)
    source_fields = fields.JSONField[dict[str, Any] | None](null=True)
    synced_at = fields.DatetimeField(null=True)
    is_removed_in_source = fields.BooleanField(default=False)
    # 백오피스가 관리하는 필드
    status = fields.CharEnumField(
        EnrollmentStatus, max_length=20, default=EnrollmentStatus.ENROLLED
    )
    enrolled_at = fields.DateField()
    ended_at = fields.DateField(null=True)
    end_reason = fields.CharField(max_length=200, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "students"
        unique_together = (("user", "cohort"),)
        indexes = (("cohort", "status"), ("name", "phone_number"))


class RosterSyncRunModel(models.Model):
    id = fields.UUIDField(primary_key=True, default=new_id)
    trigger = fields.CharEnumField(RosterSyncTrigger, max_length=20)
    scope_type = fields.CharEnumField(RosterSyncScope, max_length=20)
    bootcamp: fields.ForeignKeyNullableRelation[BootcampModel] = fields.ForeignKeyField(
        "models.BootcampModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    cohort: fields.ForeignKeyNullableRelation[CohortModel] = fields.ForeignKeyField(
        "models.CohortModel", related_name=False, null=True, on_delete=fields.RESTRICT
    )
    status = fields.CharEnumField(RosterSyncStatus, max_length=20, default=RosterSyncStatus.RUNNING)
    started_at = fields.DatetimeField()
    finished_at = fields.DatetimeField(null=True)
    fetched_count = fields.IntField(default=0)
    upserted_count = fields.IntField(default=0)
    removed_count = fields.IntField(default=0)
    unmapped_count = fields.IntField(default=0)
    unmapped_records = fields.JSONField[list[dict[str, Any]]](default=list)
    error_message = fields.TextField(null=True)

    class Meta:
        table = "roster_sync_runs"
        indexes = (("started_at",), ("cohort", "started_at"))

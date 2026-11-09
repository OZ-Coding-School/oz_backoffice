"""academy 리포지토리 구현 (Tortoise)."""

import uuid
from collections.abc import Collection
from datetime import datetime

from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
    RosterSyncRun,
    Student,
)
from app.contexts.academy.domain.enums import CohortStatus, EnrollmentStatus
from app.contexts.academy.infrastructure.models import (
    BootcampModel,
    CohortModel,
    HrdNetBootcampCohortModel,
    HrdNetBootcampModel,
    RosterSyncRunModel,
    StudentModel,
)
from app.core.persistence import TortoiseRepository


class TortoiseHrdNetBootcampRepository(TortoiseRepository[HrdNetBootcamp, HrdNetBootcampModel]):
    model = HrdNetBootcampModel
    entity = HrdNetBootcamp
    fields = (
        "name",
        "hrd_net_id",
        "train_type",
        "ncs1_se",
        "ncs2_se",
        "ncs3_se",
        "weekend_se",
        "day_night_se",
        "total_train_fee",
        "train_fee_per_hour",
        "total_train_hours",
        "total_train_days",
    )

    async def get_by_hrd_net_id(self, hrd_net_id: str) -> HrdNetBootcamp | None:
        row = await HrdNetBootcampModel.get_or_none(hrd_net_id=hrd_net_id.strip())
        return self.to_entity(row) if row else None

    async def list_all(self) -> list[HrdNetBootcamp]:
        return [self.to_entity(row) for row in await HrdNetBootcampModel.all().order_by("name")]


class TortoiseHrdNetBootcampCohortRepository(
    TortoiseRepository[HrdNetBootcampCohort, HrdNetBootcampCohortModel]
):
    model = HrdNetBootcampCohortModel
    entity = HrdNetBootcampCohort
    fields = (
        "hrd_net_bootcamp_id",
        "cohort_number",
        "train_start_date",
        "train_end_date",
        "self_pay_amount",
    )

    async def get_by_number(
        self, hrd_net_bootcamp_id: uuid.UUID, cohort_number: int
    ) -> HrdNetBootcampCohort | None:
        row = await HrdNetBootcampCohortModel.get_or_none(
            hrd_net_bootcamp_id=hrd_net_bootcamp_id, cohort_number=cohort_number
        )
        return self.to_entity(row) if row else None

    async def list_by_bootcamp(self, hrd_net_bootcamp_id: uuid.UUID) -> list[HrdNetBootcampCohort]:
        rows = await HrdNetBootcampCohortModel.filter(
            hrd_net_bootcamp_id=hrd_net_bootcamp_id
        ).order_by("cohort_number")
        return [self.to_entity(row) for row in rows]


class TortoiseBootcampRepository(TortoiseRepository[Bootcamp, BootcampModel]):
    model = BootcampModel
    entity = Bootcamp
    fields = ("hrd_net_bootcamp_id", "name", "code", "is_active", "airtable_cohort_prefix")

    async def get_by_code(self, code: str) -> Bootcamp | None:
        row = await BootcampModel.get_or_none(code=code.strip().upper())
        return self.to_entity(row) if row else None

    async def get_by_name(self, name: str) -> Bootcamp | None:
        row = await BootcampModel.get_or_none(name=name.strip())
        return self.to_entity(row) if row else None

    async def get_by_airtable_prefix(self, prefix: str) -> Bootcamp | None:
        row = await BootcampModel.get_or_none(airtable_cohort_prefix=prefix.strip())
        return self.to_entity(row) if row else None

    async def list_active(self) -> list[Bootcamp]:
        rows = await BootcampModel.filter(is_active=True).order_by("name")
        return [self.to_entity(row) for row in rows]

    async def list_all(self) -> list[Bootcamp]:
        return [self.to_entity(row) for row in await BootcampModel.all().order_by("name")]


class TortoiseCohortRepository(TortoiseRepository[Cohort, CohortModel]):
    model = CohortModel
    entity = Cohort
    fields = (
        "hrd_net_cohort_id",
        "bootcamp_id",
        "cohort_number",
        "start_date",
        "end_date",
        "status",
        "discord_guild_id",
    )

    async def get_by_number(self, bootcamp_id: uuid.UUID, cohort_number: int) -> Cohort | None:
        row = await CohortModel.get_or_none(bootcamp_id=bootcamp_id, cohort_number=cohort_number)
        return self.to_entity(row) if row else None

    async def list_by_bootcamp(self, bootcamp_id: uuid.UUID) -> list[Cohort]:
        rows = await CohortModel.filter(bootcamp_id=bootcamp_id).order_by("cohort_number")
        return [self.to_entity(row) for row in rows]

    async def list_by_statuses(self, statuses: Collection[CohortStatus]) -> list[Cohort]:
        rows = await CohortModel.filter(status__in=list(statuses)).order_by(
            "bootcamp_id", "cohort_number"
        )
        return [self.to_entity(row) for row in rows]


class TortoiseStudentRepository(TortoiseRepository[Student, StudentModel]):
    model = StudentModel
    entity = Student
    fields = (
        "user_id",
        "cohort_id",
        "airtable_record_id",
        "name",
        "phone_number",
        "email",
        "hrd_net_status",
        "source_fields",
        "synced_at",
        "is_removed_in_source",
        "status",
        "enrolled_at",
        "ended_at",
        "end_reason",
    )

    async def get_by_user_and_cohort(
        self, user_id: uuid.UUID, cohort_id: uuid.UUID
    ) -> Student | None:
        row = await StudentModel.get_or_none(user_id=user_id, cohort_id=cohort_id)
        return self.to_entity(row) if row else None

    async def list_by_user(self, user_id: uuid.UUID) -> list[Student]:
        rows = await StudentModel.filter(user_id=user_id).order_by("enrolled_at")
        return [self.to_entity(row) for row in rows]

    async def list_by_record_ids(self, airtable_record_ids: list[str]) -> list[Student]:
        if not airtable_record_ids:
            return []
        rows = await StudentModel.filter(airtable_record_id__in=airtable_record_ids)
        return [self.to_entity(row) for row in rows]

    async def list_sourced_by_cohorts(self, cohort_ids: list[uuid.UUID]) -> list[Student]:
        if not cohort_ids:
            return []
        rows = await StudentModel.filter(cohort_id__in=cohort_ids, airtable_record_id__isnull=False)
        return [self.to_entity(row) for row in rows]

    async def add_many(self, students: list[Student]) -> None:
        await StudentModel.bulk_create(
            [StudentModel(id=s.id, **self.to_values(s)) for s in students], batch_size=500
        )

    async def save_many(self, students: list[Student], *, now: datetime) -> None:
        if not students:
            return
        rows = [StudentModel(id=s.id, **self.to_values(s), updated_at=now) for s in students]
        await StudentModel.bulk_update(rows, fields=[*self.fields, "updated_at"], batch_size=500)

    async def get_by_record_id(self, airtable_record_id: str) -> Student | None:
        row = await StudentModel.get_or_none(airtable_record_id=airtable_record_id)
        return self.to_entity(row) if row else None

    async def find_claimable_by_name_and_phone(self, name: str, phone_number: str) -> list[Student]:
        rows = await StudentModel.filter(
            name=name,
            phone_number=phone_number,
            status=EnrollmentStatus.ENROLLED,
            is_removed_in_source=False,
            user_id__isnull=True,
        ).order_by("id")
        return [self.to_entity(row) for row in rows]


class TortoiseRosterSyncRunRepository(TortoiseRepository[RosterSyncRun, RosterSyncRunModel]):
    model = RosterSyncRunModel
    entity = RosterSyncRun
    fields = (
        "trigger",
        "scope_type",
        "bootcamp_id",
        "cohort_id",
        "status",
        "started_at",
        "finished_at",
        "fetched_count",
        "upserted_count",
        "removed_count",
        "unmapped_count",
        "unmapped_records",
        "error_message",
    )

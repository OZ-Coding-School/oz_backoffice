"""academy 리포지토리 구현 (Tortoise)."""

import uuid

from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
    RosterSyncRun,
    Student,
    StudentRoster,
)
from app.contexts.academy.infrastructure.models import (
    BootcampModel,
    CohortModel,
    HrdNetBootcampCohortModel,
    HrdNetBootcampModel,
    RosterSyncRunModel,
    StudentModel,
    StudentRosterModel,
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


class TortoiseBootcampRepository(TortoiseRepository[Bootcamp, BootcampModel]):
    model = BootcampModel
    entity = Bootcamp
    fields = ("hrd_net_bootcamp_id", "name", "code", "is_active")

    async def get_by_code(self, code: str) -> Bootcamp | None:
        row = await BootcampModel.get_or_none(code=code.strip().upper())
        return self.to_entity(row) if row else None


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


class TortoiseStudentRepository(TortoiseRepository[Student, StudentModel]):
    model = StudentModel
    entity = Student
    fields = (
        "user_id",
        "cohort_id",
        "status",
        "hrd_net_status",
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


class TortoiseStudentRosterRepository(TortoiseRepository[StudentRoster, StudentRosterModel]):
    model = StudentRosterModel
    entity = StudentRoster
    fields = (
        "airtable_record_id",
        "cohort_id",
        "name",
        "phone_number",
        "email",
        "hrd_net_status",
        "source_fields",
        "is_removed_in_source",
        "matched_student_id",
        "synced_at",
    )

    async def get_by_record_id(self, airtable_record_id: str) -> StudentRoster | None:
        row = await StudentRosterModel.get_or_none(airtable_record_id=airtable_record_id)
        return self.to_entity(row) if row else None

    async def find_unmatched_by_name_and_phone(
        self, name: str, phone_number: str
    ) -> list[StudentRoster]:
        rows = await StudentRosterModel.filter(
            name=name,
            phone_number=phone_number,
            cohort_id__isnull=False,
            is_removed_in_source=False,
            matched_student_id__isnull=True,
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
        "error_message",
    )

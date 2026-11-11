"""mentoring 리포지토리 구현 (Tortoise)."""

import uuid
from datetime import UTC, date
from typing import Any

from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.schedule import (
    MentorUnavailablePeriod,
    mask_to_weekdays,
    weekdays_to_mask,
)
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
    OperatingHours,
)
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.models import (
    CohortMentoringBlockTimeModel,
    CohortMentoringSettingsModel,
    CohortMentorModel,
    MentoringBalanceAccountModel,
    MentoringBalanceTransactionModel,
    MentoringHolidayModel,
    MentoringTeamMemberModel,
    MentoringTeamModel,
    MentorUnavailablePeriodModel,
)
from app.core.persistence import TortoiseRepository
from app.shared.errors import ConflictError
from app.shared.ids import new_id

ACTIVE_ASSIGNMENT_INDEX = "uid_cohort_mentors_active"


class TortoiseCohortMentoringSettingsRepository(
    TortoiseRepository[CohortMentoringSettings, CohortMentoringSettingsModel]
):
    model = CohortMentoringSettingsModel
    entity = CohortMentoringSettings
    fields = (
        "cohort_id",
        "allow_team_mentoring",
        "allow_1_on_1",
        "default_1on1_minutes",
        "default_team_minutes",
        "min_lead_hours",
        "allowed_duration",
        "max_pending_requests",
    )

    def to_entity(self, row: CohortMentoringSettingsModel) -> CohortMentoringSettings:
        entity = super().to_entity(row)
        entity.weekday_hours = _hours(row.weekday_open_minute, row.weekday_close_minute)
        entity.weekend_hours = _hours(row.weekend_open_minute, row.weekend_close_minute)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    def to_values(self, entity: CohortMentoringSettings) -> dict[str, Any]:
        values = super().to_values(entity)
        for prefix, hours in (("weekday", entity.weekday_hours), ("weekend", entity.weekend_hours)):
            values[f"{prefix}_open_minute"] = hours.start_minute if hours else None
            values[f"{prefix}_close_minute"] = hours.end_minute if hours else None
        return values

    async def get_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        row = await CohortMentoringSettingsModel.get_or_none(cohort_id=cohort_id)
        return self.to_entity(row) if row else None

    async def lock_by_cohort(self, cohort_id: uuid.UUID) -> CohortMentoringSettings | None:
        row = await CohortMentoringSettingsModel.select_for_update().get_or_none(
            cohort_id=cohort_id
        )
        return self.to_entity(row) if row else None


def _hours(open_minute: int | None, close_minute: int | None) -> OperatingHours | None:
    if open_minute is None or close_minute is None:
        return None
    return OperatingHours(start_minute=open_minute, end_minute=close_minute)


class TortoiseMentoringBlockTimeRepository(
    TortoiseRepository[MentoringBlockTime, CohortMentoringBlockTimeModel]
):
    model = CohortMentoringBlockTimeModel
    entity = MentoringBlockTime
    fields = ("cohort_id", "period_start", "period_end", "start_time", "end_time", "reason")

    def to_entity(self, row: CohortMentoringBlockTimeModel) -> MentoringBlockTime:
        # 컬럼은 시간대 없는 TIME(한국 시각 "시:분")이다. Tortoise(use_tz)가 붙이는 UTC를 뗀다
        entity = super().to_entity(row)
        entity.start_time = entity.start_time.replace(tzinfo=None)
        entity.end_time = entity.end_time.replace(tzinfo=None)
        return entity

    def to_values(self, entity: MentoringBlockTime) -> dict[str, Any]:
        # Tortoise(use_tz)가 시간대 없는 시각에 경고를 내므로 표시만 붙여 넘긴다
        # (TIME 컬럼에는 시:분만 저장된다)
        values = super().to_values(entity)
        values["start_time"] = entity.start_time.replace(tzinfo=UTC)
        values["end_time"] = entity.end_time.replace(tzinfo=UTC)
        return values

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringBlockTime]:
        rows = await CohortMentoringBlockTimeModel.filter(cohort_id=cohort_id).order_by(
            "period_start", "start_time", "id"
        )
        return [self.to_entity(row) for row in rows]


class TortoiseMentoringHolidayRepository(
    TortoiseRepository[MentoringHoliday, MentoringHolidayModel]
):
    model = MentoringHolidayModel
    entity = MentoringHoliday
    fields = ("holiday_date", "name")

    async def get_by_date(self, day: date) -> MentoringHoliday | None:
        row = await MentoringHolidayModel.get_or_none(holiday_date=day)
        return self.to_entity(row) if row else None

    async def list_between(self, start: date, end: date) -> list[MentoringHoliday]:
        rows = await MentoringHolidayModel.filter(
            holiday_date__gte=start, holiday_date__lte=end
        ).order_by("holiday_date")
        return [self.to_entity(row) for row in rows]


class TortoiseCohortMentorRepository(TortoiseRepository[CohortMentor, CohortMentorModel]):
    model = CohortMentorModel
    entity = CohortMentor
    fields = (
        "cohort_id",
        "mentor_id",
        "start_date",
        "end_date",
        "cost_settlement_policy",
        "pay_unit",
        "pay_rate",
        "no_show_pay_amount",
        "is_active",
        "deactivated_at",
        "deactivation_reason",
    )

    def to_entity(self, row: CohortMentorModel) -> CohortMentor:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    async def add(self, entity: CohortMentor) -> None:
        await self._guard(super().add(entity))

    async def save(self, entity: CohortMentor) -> None:
        await self._guard(super().save(entity))

    @staticmethod
    async def _guard(operation: Any) -> None:
        """동시 요청이 서비스 검사를 지나도 부분 유니크가 막는다 → 409."""
        try:
            await operation
        except IntegrityError as exc:
            if ACTIVE_ASSIGNMENT_INDEX not in str(exc):
                raise
            raise ConflictError(
                "이 기수에 이미 활성 배정된 멘토입니다.", code="assignment_already_exists"
            ) from exc

    async def list_by_ids(self, assignment_ids: list[uuid.UUID]) -> list[CohortMentor]:
        if not assignment_ids:
            return []
        rows = await CohortMentorModel.filter(id__in=assignment_ids)
        return [self.to_entity(row) for row in rows]

    async def find_active(self, mentor_id: uuid.UUID, cohort_id: uuid.UUID) -> CohortMentor | None:
        row = await CohortMentorModel.get_or_none(
            mentor_id=mentor_id, cohort_id=cohort_id, is_active=True
        )
        return self.to_entity(row) if row else None

    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]:
        query = CohortMentorModel.filter(cohort_id=cohort_id)
        if not include_inactive:
            query = query.filter(is_active=True)
        rows = await query.order_by("-is_active", "start_date", "id")
        return [self.to_entity(row) for row in rows]

    async def list_by_mentor(
        self, mentor_id: uuid.UUID, *, include_inactive: bool
    ) -> list[CohortMentor]:
        query = CohortMentorModel.filter(mentor_id=mentor_id)
        if not include_inactive:
            query = query.filter(is_active=True)
        rows = await query.order_by("-is_active", "-start_date", "id")
        return [self.to_entity(row) for row in rows]

    async def list_expired(self, today: date) -> list[CohortMentor]:
        rows = await CohortMentorModel.filter(is_active=True, end_date__lt=today).order_by("id")
        return [self.to_entity(row) for row in rows]


class TortoiseMentorUnavailablePeriodRepository(
    TortoiseRepository[MentorUnavailablePeriod, MentorUnavailablePeriodModel]
):
    model = MentorUnavailablePeriodModel
    entity = MentorUnavailablePeriod
    fields = ("mentor_id", "repeat", "starts_at", "ends_at", "repeat_until", "category", "reason")

    def to_entity(self, row: MentorUnavailablePeriodModel) -> MentorUnavailablePeriod:
        entity = MentorUnavailablePeriod(
            id=row.id,
            weekdays=mask_to_weekdays(row.weekdays_mask),
            **{name: getattr(row, name) for name in self.fields},
        )
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    def to_values(self, entity: MentorUnavailablePeriod) -> dict[str, Any]:
        values = super().to_values(entity)
        values["weekdays_mask"] = weekdays_to_mask(entity.weekdays)
        return values

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentorUnavailablePeriod]:
        rows = await MentorUnavailablePeriodModel.filter(mentor_id=mentor_id).order_by(
            "starts_at", "id"
        )
        return [self.to_entity(row) for row in rows]


class TortoiseMentoringTeamRepository:
    """팀과 팀원을 함께 다룬다 (팀원은 루트와 함께 저장)."""

    async def add(self, team: MentoringTeam) -> None:
        await MentoringTeamModel.create(
            id=team.id,
            cohort_id=team.cohort_id,
            mentor_id=team.mentor_id,
            team_number=team.team_number,
            name=team.name,
        )
        await self._insert_members(team, team.member_ids)

    async def save(self, team: MentoringTeam) -> None:
        await MentoringTeamModel.filter(id=team.id).update(mentor_id=team.mentor_id, name=team.name)
        row = await MentoringTeamModel.get(id=team.id)
        await row.save(update_fields=["updated_at"])  # auto_now 갱신
        current = set(
            await MentoringTeamMemberModel.filter(team_id=team.id).values_list(
                "student_id", flat=True
            )
        )
        wanted = set(team.member_ids)
        if removed := current - wanted:
            await MentoringTeamMemberModel.filter(
                team_id=team.id, student_id__in=list(removed)
            ).delete()
        await self._insert_members(team, [s for s in team.member_ids if s not in current])

    async def get(self, team_id: uuid.UUID) -> MentoringTeam | None:
        row = await MentoringTeamModel.get_or_none(id=team_id)
        if row is None:
            return None
        return (await self._with_members([row]))[0]

    async def delete(self, team_id: uuid.UUID) -> None:
        try:
            await MentoringTeamModel.filter(id=team_id).delete()
        except IntegrityError as exc:
            raise ConflictError(
                "시간 계좌나 신청이 있는 팀은 삭제할 수 없습니다.", code="team_in_use"
            ) from exc

    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringTeam]:
        rows = await MentoringTeamModel.filter(cohort_id=cohort_id).order_by("team_number")
        return await self._with_members(rows)

    async def next_number(self, cohort_id: uuid.UUID) -> int:
        top = await MentoringTeamModel.filter(cohort_id=cohort_id).order_by("-team_number").first()
        return top.team_number + 1 if top else 1

    async def team_of_students(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        if not student_ids:
            return {}
        rows = await MentoringTeamMemberModel.filter(student_id__in=student_ids).values_list(
            "student_id", "team_id"
        )
        return {student_id: team_id for student_id, team_id in rows}

    async def list_by_students(self, student_ids: list[uuid.UUID]) -> list[MentoringTeam]:
        if not student_ids:
            return []
        team_ids = await MentoringTeamMemberModel.filter(student_id__in=student_ids).values_list(
            "team_id", flat=True
        )
        rows = await MentoringTeamModel.filter(id__in=list(set(team_ids))).order_by(
            "cohort_id", "team_number"
        )
        return await self._with_members(rows)

    async def list_memberships(self) -> list[tuple[uuid.UUID, uuid.UUID]]:
        rows = await MentoringTeamMemberModel.all().values_list("team_id", "student_id")
        return [(team_id, student_id) for team_id, student_id in rows]

    async def remove_memberships(self, pairs: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
        if not pairs:
            return
        condition = Q()
        for team_id, student_id in pairs:
            condition |= Q(team_id=team_id, student_id=student_id)
        await MentoringTeamMemberModel.filter(condition).delete()

    async def list_by_ids(self, team_ids: list[uuid.UUID]) -> list[MentoringTeam]:
        if not team_ids:
            return []
        return await self._with_members(await MentoringTeamModel.filter(id__in=team_ids))

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[MentoringTeam]:
        rows = await MentoringTeamModel.filter(mentor_id=mentor_id).order_by(
            "cohort_id", "team_number"
        )
        return await self._with_members(rows)

    @staticmethod
    async def _insert_members(team: MentoringTeam, student_ids: list[uuid.UUID]) -> None:
        if not student_ids:
            return
        try:
            await MentoringTeamMemberModel.bulk_create(
                [
                    MentoringTeamMemberModel(
                        id=new_id(),
                        team_id=team.id,
                        student_id=student_id,
                    )
                    for student_id in student_ids
                ]
            )
        except IntegrityError as exc:
            raise ConflictError(
                "이미 다른 팀에 속한 수강생이 있습니다.", code="student_in_other_team"
            ) from exc

    @staticmethod
    async def _with_members(rows: list[MentoringTeamModel]) -> list[MentoringTeam]:
        members: dict[uuid.UUID, list[uuid.UUID]] = {row.id: [] for row in rows}
        if rows:
            for team_id, student_id in (
                await MentoringTeamMemberModel.filter(team_id__in=list(members))
                .order_by("created_at", "id")
                .values_list("team_id", "student_id")
            ):
                members[team_id].append(student_id)
        return [
            MentoringTeam(
                id=row.id,
                cohort_id=row.cohort_id,  # type: ignore[attr-defined]  # FK 컬럼 속성
                mentor_id=row.mentor_id,  # type: ignore[attr-defined]
                team_number=row.team_number,
                name=row.name,
                member_ids=members[row.id],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]


class TortoiseBalanceAccountRepository(
    TortoiseRepository[BalanceAccount, MentoringBalanceAccountModel]
):
    model = MentoringBalanceAccountModel
    entity = BalanceAccount
    fields = (
        "student_id",
        "team_id",
        "valid_from",
        "valid_until",
        "total_minutes",
        "held_minutes",
        "used_minutes",
    )

    def to_entity(self, row: MentoringBalanceAccountModel) -> BalanceAccount:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    def to_values(self, entity: BalanceAccount) -> dict[str, Any]:
        values = super().to_values(entity)
        values["remaining_minutes"] = entity.remaining_minutes
        return values

    async def add(self, entity: BalanceAccount) -> None:
        try:
            await super().add(entity)
        except IntegrityError as exc:
            raise ConflictError(
                "이미 계좌가 있습니다. 다시 시도하세요.", code="balance_account_exists"
            ) from exc

    async def lock_many(self, account_ids: list[uuid.UUID]) -> list[BalanceAccount]:
        if not account_ids:
            return []
        rows = (
            await MentoringBalanceAccountModel.filter(id__in=account_ids)
            .order_by("id")
            .select_for_update()
        )
        return [self.to_entity(row) for row in rows]

    async def find_by_owners(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
    ) -> list[BalanceAccount]:
        if not student_ids and not team_ids:
            return []
        rows = await MentoringBalanceAccountModel.filter(
            Q(student_id__in=student_ids) | Q(team_id__in=team_ids)
        ).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_student_accounts_with_remaining(self) -> list[BalanceAccount]:
        rows = await MentoringBalanceAccountModel.filter(
            student_id__isnull=False, remaining_minutes__gt=0
        ).order_by("id")
        return [self.to_entity(row) for row in rows]

    async def list_page(
        self,
        cohort_id: uuid.UUID,
        *,
        owner: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BalanceAccount], int]:
        condition = Q(student__cohort_id=cohort_id) | Q(team__cohort_id=cohort_id)
        if owner == "STUDENT":
            condition = Q(student__cohort_id=cohort_id)
        elif owner == "TEAM":
            condition = Q(team__cohort_id=cohort_id)
        query = MentoringBalanceAccountModel.filter(condition)
        total = await query.count()
        rows = await query.order_by("id").offset(offset).limit(limit)
        return [self.to_entity(row) for row in rows], total


class TortoiseBalanceTransactionRepository:
    async def add_many(self, entries: list[BalanceTransaction]) -> None:
        if not entries:
            return
        await MentoringBalanceTransactionModel.bulk_create(
            [
                MentoringBalanceTransactionModel(
                    id=e.id,
                    account_id=e.account_id,
                    request_id=e.request_id,
                    type=e.type,
                    amount=e.amount,
                    after_remaining=e.after_remaining,
                    after_held=e.after_held,
                    reason=e.reason,
                )
                for e in entries
            ]
        )

    async def list_by_account(
        self, account_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BalanceTransaction]:
        query = MentoringBalanceTransactionModel.filter(account_id=account_id)
        if before is not None:
            query = query.filter(id__lt=before)
        rows = await query.order_by("-id").limit(limit)
        return [
            BalanceTransaction(
                id=row.id,
                account_id=row.account_id,  # type: ignore[attr-defined]  # FK 컬럼 속성
                request_id=row.request_id,
                type=row.type,
                amount=row.amount,
                after_remaining=row.after_remaining,
                after_held=row.after_held,
                reason=row.reason,
                created_at=row.created_at,
            )
            for row in rows
        ]

"""멘토링 시간 계좌 지급·조정·조회 (decisions M8·M9·M10·A39·A40, 권한 mentoring.balance.grant).

- 지급(개별·일괄): 대상은 기수 전체 수강 중 수강생 / 고른 수강생 / 기수의 모든 팀 / 고른 팀.
  계좌가 없으면 만들고 사용 기간을 정한다(기본: 기수 시작일~종료일, 기수 기간 안).
  이미 있으면 기간은 그대로 두고 더한다. 분을 비우면 기수 설정의 기본 지급 시간.
  가능한 대상만 지급하고 만료·수강 종료·다른 기수 등은 사유와 함께 돌려준다(한 트랜잭션).
- 조정(±): 잔여는 음수 불가, 만료 계좌는 차감만.
- 계좌 행은 id 순서로 잠그고 원장과 같은 트랜잭션에서 바꾼다.
- 처리자는 감사 로그로 남긴다(M25).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Protocol

from app.contexts.academy.domain.entities import Cohort, Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.domain.balance import (
    BalanceAccount,
    BalanceTransaction,
    clean_reason,
    ensure_grant_minutes,
    ensure_validity,
)
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    CohortMentoringSettingsRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import AppError, BusinessRuleViolation, NotFoundError
from app.shared.time import business_date

TARGET = "mentoring_balance_account"


class GrantTarget(StrEnum):
    ALL_STUDENTS = "ALL_STUDENTS"  # 기수 전체 수강 중 수강생 (1:1)
    STUDENTS = "STUDENTS"  # 고른 수강생 (1:1)
    ALL_TEAMS = "ALL_TEAMS"  # 기수의 모든 팀
    TEAMS = "TEAMS"  # 고른 팀


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...
    async def enrolled_in_cohort(self, cohort_id: uuid.UUID) -> list[Student]: ...
    async def of_user(self, user_id: uuid.UUID) -> list[Student]: ...


class CohortLookup(Protocol):
    """academy `AcademyCatalog`."""

    async def get_cohort(self, cohort_id: uuid.UUID) -> Cohort | None: ...


@dataclass(frozen=True, slots=True)
class Granted:
    owner_id: uuid.UUID
    account_id: uuid.UUID
    minutes: int
    created: bool  # 이번 지급으로 계좌를 만들었는지


@dataclass(frozen=True, slots=True)
class Skipped:
    owner_id: uuid.UUID
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class GrantResult:
    granted: list[Granted] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Owners:
    """계좌 소유자 표시 정보."""

    students: dict[uuid.UUID, Student]
    teams: dict[uuid.UUID, MentoringTeam]


@dataclass(frozen=True, slots=True)
class _Owner:
    id: uuid.UUID
    is_team: bool


class BalanceService:
    def __init__(
        self,
        *,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        teams: MentoringTeamRepository,
        settings: CohortMentoringSettingsRepository,
        students: StudentLookup,
        cohorts: CohortLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._accounts = accounts
        self._ledger = ledger
        self._teams = teams
        self._settings = settings
        self._students = students
        self._cohorts = cohorts
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 지급
    async def grant(
        self,
        cohort_id: uuid.UUID,
        *,
        target: GrantTarget,
        ids: list[uuid.UUID],
        minutes: int | None,
        valid_from: date | None,
        valid_until: date | None,
        reason: str,
        actor_id: uuid.UUID,
    ) -> GrantResult:
        cohort = await self._cohort(cohort_id)
        is_team = target in (GrantTarget.ALL_TEAMS, GrantTarget.TEAMS)
        amount = minutes if minutes is not None else await self._default_minutes(cohort_id, is_team)
        start, end = valid_from or cohort.start_date, valid_until or cohort.end_date
        ensure_validity(start, end, cohort_start=cohort.start_date, cohort_end=cohort.end_date)
        ensure_grant_minutes(amount)  # 요청 전체의 오류는 대상별로 건너뛰지 않고 거부한다
        reason = clean_reason(reason)
        today = business_date(self._clock.now())
        owners, skipped = await self._resolve(cohort_id, target, ids)

        granted: list[Granted] = []
        async with self._uow:
            existing = await self._accounts.find_by_owners(
                student_ids=[o.id for o in owners if not o.is_team],
                team_ids=[o.id for o in owners if o.is_team],
            )
            locked = await self._accounts.lock_many([a.id for a in existing])
            by_owner = {owner_of(a): a for a in locked}
            entries: list[BalanceTransaction] = []
            for owner in owners:
                account = by_owner.get(owner.id)
                created = account is None
                if account is None:
                    account = BalanceAccount(
                        student_id=None if owner.is_team else owner.id,
                        team_id=owner.id if owner.is_team else None,
                        valid_from=start,
                        valid_until=end,
                    )
                try:
                    entries.append(account.grant(amount, reason, today=today))
                except AppError as error:
                    skipped.append(Skipped(owner.id, error.code, error.message))
                    continue
                if created:
                    await self._accounts.add(account)
                else:
                    await self._accounts.save(account)
                granted.append(Granted(owner.id, account.id, amount, created))
            await self._ledger.add_many(entries)
            if granted:
                await self._audit.record(
                    actor_user_id=actor_id,
                    action="mentoring.balance.grant",
                    target_type="cohort",
                    target_id=cohort_id,
                    after={
                        "target": target.value,
                        "minutes": amount,
                        "reason": reason,
                        "accounts": [str(g.account_id) for g in granted],
                        "skipped": len(skipped),
                    },
                )
        return GrantResult(granted=granted, skipped=skipped)

    # ------------------------------------------------------------------ 조정·기간
    async def adjust(
        self,
        cohort_id: uuid.UUID,
        account_id: uuid.UUID,
        delta: int,
        reason: str,
        *,
        actor_id: uuid.UUID,
    ) -> BalanceAccount:
        today = business_date(self._clock.now())
        async with self._uow:
            account = await self._locked_in_cohort(cohort_id, account_id)
            before = account.remaining_minutes
            entry = account.adjust(delta, reason, today=today)
            await self._accounts.save(account)
            await self._ledger.add_many([entry])
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.balance.adjust",
                target_type=TARGET,
                target_id=account_id,
                before={"remaining_minutes": before},
                after={
                    "remaining_minutes": account.remaining_minutes,
                    "amount": delta,
                    "reason": entry.reason,
                },
            )
        return account

    async def change_validity(
        self,
        cohort_id: uuid.UUID,
        account_id: uuid.UUID,
        valid_from: date,
        valid_until: date,
        *,
        actor_id: uuid.UUID,
    ) -> BalanceAccount:
        cohort = await self._cohort(cohort_id)
        async with self._uow:
            account = await self._locked_in_cohort(cohort_id, account_id)
            before = {
                "valid_from": str(account.valid_from),
                "valid_until": str(account.valid_until),
            }
            account.change_validity(
                valid_from, valid_until, cohort_start=cohort.start_date, cohort_end=cohort.end_date
            )
            await self._accounts.save(account)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.balance.validity",
                target_type=TARGET,
                target_id=account_id,
                before=before,
                after={"valid_from": str(valid_from), "valid_until": str(valid_until)},
            )
        return account

    # ------------------------------------------------------------------ 조회
    async def list_accounts(
        self,
        cohort_id: uuid.UUID,
        *,
        owner: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[BalanceAccount], int]:
        return await self._accounts.list_page(cohort_id, owner=owner, limit=limit, offset=offset)

    async def transactions(
        self, cohort_id: uuid.UUID, account_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BalanceTransaction]:
        account = await self._accounts.get(account_id)
        if account is None or await self._cohort_of(account) != cohort_id:
            raise NotFoundError("크레딧 정보를 찾을 수 없습니다.", code="balance_account_not_found")
        return await self._ledger.list_by_account(account_id, before=before, limit=limit)

    async def mine(self, user_id: uuid.UUID) -> list[BalanceAccount]:
        """본인 1:1 계좌와 소속 팀 계좌."""
        students = await self._students.of_user(user_id)
        teams = await self._teams.list_by_students([s.id for s in students])
        return await self._accounts.find_by_owners(
            student_ids=[s.id for s in students],
            team_ids=[t.id for t in teams],
        )

    async def my_transactions(
        self, user_id: uuid.UUID, account_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[BalanceTransaction]:
        if account_id not in {a.id for a in await self.mine(user_id)}:
            raise NotFoundError("크레딧 정보를 찾을 수 없습니다.", code="balance_account_not_found")
        return await self._ledger.list_by_account(account_id, before=before, limit=limit)

    async def owners_of(self, accounts: list[BalanceAccount]) -> Owners:
        student_ids = [a.student_id for a in accounts if a.student_id is not None]
        team_ids = list({a.team_id for a in accounts if a.team_id is not None})
        teams = {t.id: t for t in await self._teams.list_by_ids(team_ids)}
        return Owners(students=await self._students.get_many(student_ids), teams=teams)

    # ------------------------------------------------------------------ 내부
    async def _cohort(self, cohort_id: uuid.UUID) -> Cohort:
        cohort = await self._cohorts.get_cohort(cohort_id)
        if cohort is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")
        return cohort

    async def _default_minutes(self, cohort_id: uuid.UUID, is_team: bool) -> int:
        settings = await self._settings.get_by_cohort(cohort_id)
        if settings is None:
            raise NotFoundError(
                "기본 지급 크레딧을 쓰려면 기수 멘토링 설정이 필요합니다.",
                code="mentoring_settings_not_configured",
            )
        return settings.default_team_minutes if is_team else settings.default_1on1_minutes

    async def _resolve(
        self,
        cohort_id: uuid.UUID,
        target: GrantTarget,
        ids: list[uuid.UUID],
    ) -> tuple[list[_Owner], list[Skipped]]:
        skipped: list[Skipped] = []
        if target is GrantTarget.ALL_STUDENTS:
            students = await self._students.enrolled_in_cohort(cohort_id)
            return [_Owner(s.id, False) for s in students], skipped
        if target is GrantTarget.ALL_TEAMS:
            teams = await self._teams.list_by_cohort(cohort_id)
            return [_Owner(t.id, True) for t in teams], skipped
        wanted = list(dict.fromkeys(ids))
        if not wanted:
            raise BusinessRuleViolation(
                "지급 대상을 하나 이상 고르세요.", code="grant_target_required"
            )
        owners: list[_Owner] = []
        if target is GrantTarget.STUDENTS:
            found = await self._students.get_many(wanted)
            enrolled = {s.id for s in await self._students.enrolled_in_cohort(cohort_id)}
            for student_id in wanted:
                student = found.get(student_id)
                if student is None or student.cohort_id != cohort_id:
                    skipped.append(
                        Skipped(student_id, "student_not_found", "이 기수의 수강생이 아닙니다.")
                    )
                elif student_id not in enrolled:
                    skipped.append(
                        Skipped(student_id, "student_not_enrolled", "수강 중인 수강생이 아닙니다.")
                    )
                else:
                    owners.append(_Owner(student_id, False))
            return owners, skipped
        for team_id in wanted:
            team = await self._teams.get(team_id)
            if team is None or team.cohort_id != cohort_id:
                skipped.append(Skipped(team_id, "team_not_found", "이 기수의 팀이 아닙니다."))
            else:
                owners.append(_Owner(team_id, True))
        return owners, skipped

    async def _cohort_of(self, account: BalanceAccount) -> uuid.UUID | None:
        if account.team_id is not None:
            team = await self._teams.get(account.team_id)
            return team.cohort_id if team else None
        student_id = owner_of(account)
        student = (await self._students.get_many([student_id])).get(student_id)
        return student.cohort_id if student else None

    async def _locked_in_cohort(
        self, cohort_id: uuid.UUID, account_id: uuid.UUID
    ) -> BalanceAccount:
        locked = await self._accounts.lock_many([account_id])
        if not locked or await self._cohort_of(locked[0]) != cohort_id:
            raise NotFoundError("크레딧 정보를 찾을 수 없습니다.", code="balance_account_not_found")
        return locked[0]


def owner_of(account: BalanceAccount) -> uuid.UUID:
    owner = account.team_id if account.team_id is not None else account.student_id
    if owner is None:  # 도메인 불변식상 없지만 타입을 좁힌다
        raise NotFoundError("크레딧 소유자가 없습니다.", code="balance_owner_missing")
    return owner

"""시간 계좌 지급·조정·조회 서비스 (인메모리 + 고정 시계, A39·A40)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Cohort, Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.balance_service import BalanceService, GrantTarget
from app.contexts.mentoring.domain.settings import CohortMentoringSettings
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemorySettingsRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)
ACTOR = new_id()


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, cohort_id: uuid.UUID, **overrides: Any) -> Student:
        values: dict[str, Any] = {
            "cohort_id": cohort_id,
            "name": f"수강생{len(self.items) + 1}",
            "hrd_net_status": StudentStatus.TRAINING,
            "enrolled_at": date(2026, 11, 1),
        }
        values.update(overrides)
        student = Student(**values)
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}

    async def enrolled_in_cohort(self, cohort_id: uuid.UUID) -> list[Student]:
        return [
            s
            for s in self.items.values()
            if s.cohort_id == cohort_id and s.is_enrolled and not s.is_removed_in_source
        ]

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


class Cohorts:
    def __init__(self, *cohorts: Cohort) -> None:
        self.items = {c.id: c for c in cohorts}

    async def get_cohort(self, cohort_id: uuid.UUID) -> Cohort | None:
        return self.items.get(cohort_id)


class Harness:
    def __init__(self) -> None:
        self.cohort = Cohort(
            hrd_net_cohort_id=new_id(),
            bootcamp_id=new_id(),
            cohort_number=1,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 4, 30),
        )
        self.students = Students()
        self.teams = InMemoryTeamRepository()
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.settings = InMemorySettingsRepository(
            CohortMentoringSettings(
                cohort_id=self.cohort.id,
                allow_1_on_1=True,
                allow_team_mentoring=True,
                default_1on1_minutes=240,
                default_team_minutes=120,
            )
        )
        self.clock = FixedClock(NOW)
        self.audit_logs = InMemoryAuditLogRepository()
        self.service = BalanceService(
            accounts=self.accounts,
            ledger=self.ledger,
            teams=self.teams,
            settings=self.settings,
            students=self.students,
            cohorts=Cohorts(self.cohort),
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def team(self, cohort_id: uuid.UUID | None = None) -> MentoringTeam:
        team = MentoringTeam(
            cohort_id=cohort_id or self.cohort.id,
            team_number=len(self.teams.items) + 1,
            mentor_id=new_id(),
        )
        await self.teams.add(team)
        return team

    async def grant(self, target: GrantTarget, *ids: uuid.UUID, **overrides: Any) -> Any:
        values: dict[str, Any] = {
            "target": target,
            "ids": list(ids),
            "minutes": None,
            "valid_from": None,
            "valid_until": None,
            "reason": "기본 지급",
            "actor_id": ACTOR,
        }
        values.update(overrides)
        return await self.service.grant(self.cohort.id, **values)


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_grant_all_students_with_defaults(h: Harness) -> None:
    a = h.students.add(h.cohort.id)
    b = h.students.add(h.cohort.id)  # 미가입도 대상
    h.students.add(h.cohort.id, status=EnrollmentStatus.DROPPED)  # 제외
    result = await h.grant(GrantTarget.ALL_STUDENTS)
    assert {g.owner_id for g in result.granted} == {a.id, b.id}
    assert all(g.minutes == 240 and g.created for g in result.granted)
    account = next(iter(h.accounts.items.values()))
    assert (account.valid_from, account.valid_until) == (date(2026, 11, 1), date(2027, 4, 30))

    again = await h.grant(GrantTarget.STUDENTS, a.id, minutes=60, valid_from=date(2026, 12, 1))
    (granted,) = again.granted
    assert (granted.created, granted.minutes) == (False, 60)
    stored = h.accounts.items[granted.account_id]
    assert (stored.total_minutes, stored.valid_from) == (300, date(2026, 11, 1))  # 기간 유지
    assert len(h.ledger.entries) == 3
    assert [log.action for log in h.audit_logs.logs] == ["mentoring.balance.grant"] * 2


async def test_grant_skips_with_reasons(h: Harness) -> None:
    ok = h.students.add(h.cohort.id)
    dropped = h.students.add(h.cohort.id, status=EnrollmentStatus.COMPLETED)
    other = h.students.add(new_id())
    expired_owner = h.students.add(h.cohort.id)
    first = await h.grant(GrantTarget.STUDENTS, expired_owner.id)
    await h.service.change_validity(
        h.cohort.id,
        first.granted[0].account_id,
        date(2026, 11, 1),
        date(2026, 11, 5),
        actor_id=ACTOR,
    )
    missing = new_id()
    result = await h.grant(
        GrantTarget.STUDENTS, ok.id, dropped.id, other.id, expired_owner.id, missing
    )
    assert [g.owner_id for g in result.granted] == [ok.id]
    assert {(s.owner_id, s.code) for s in result.skipped} == {
        (dropped.id, "student_not_enrolled"),
        (other.id, "student_not_found"),
        (missing, "student_not_found"),
        (expired_owner.id, "balance_account_expired"),
    }


async def test_grant_teams(h: Harness) -> None:
    first = await h.team()
    second = await h.team()
    elsewhere = await h.team(new_id())  # 다른 기수의 팀
    result = await h.grant(GrantTarget.ALL_TEAMS)
    assert [(g.owner_id, g.minutes) for g in result.granted] == [(first.id, 120), (second.id, 120)]
    picked = await h.grant(GrantTarget.TEAMS, elsewhere.id, first.id)
    assert [g.owner_id for g in picked.granted] == [first.id]
    assert [s.code for s in picked.skipped] == ["team_not_found"]


async def test_grant_validation(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as outside:
        await h.grant(GrantTarget.ALL_STUDENTS, valid_until=date(2027, 5, 1))
    assert outside.value.code == "balance_validity_outside_cohort"
    with pytest.raises(BusinessRuleViolation):
        await h.grant(GrantTarget.ALL_STUDENTS, reason=" ")
    with pytest.raises(BusinessRuleViolation) as no_target:
        await h.grant(GrantTarget.STUDENTS)
    assert no_target.value.code == "grant_target_required"
    h.students.add(h.cohort.id)
    with pytest.raises(BusinessRuleViolation) as odd:  # 60분 단위
        await h.grant(GrantTarget.ALL_STUDENTS, minutes=90)
    assert odd.value.code == "invalid_balance_minutes"
    del h.settings.items[h.cohort.id]
    with pytest.raises(NotFoundError):  # 기본 분을 쓰려면 설정 필요
        await h.grant(GrantTarget.ALL_STUDENTS)
    await h.grant(GrantTarget.ALL_STUDENTS, minutes=60)  # 분을 주면 설정 없이도 된다
    with pytest.raises(NotFoundError):
        await h.service.grant(
            new_id(),
            target=GrantTarget.ALL_STUDENTS,
            ids=[],
            minutes=60,
            valid_from=None,
            valid_until=None,
            reason="지급",
            actor_id=ACTOR,
        )


async def test_adjust_validity_and_ledger(h: Harness) -> None:
    student = h.students.add(h.cohort.id, user_id=new_id())
    result = await h.grant(GrantTarget.STUDENTS, student.id, minutes=120)
    account_id = result.granted[0].account_id
    account = await h.service.adjust(h.cohort.id, account_id, -60, "정정", actor_id=ACTOR)
    assert account.remaining_minutes == 60
    with pytest.raises(BusinessRuleViolation):
        await h.service.adjust(h.cohort.id, account_id, -120, "초과", actor_id=ACTOR)
    with pytest.raises(NotFoundError):
        await h.service.adjust(new_id(), account_id, 60, "다른 기수", actor_id=ACTOR)

    changed = await h.service.change_validity(
        h.cohort.id, account_id, date(2026, 11, 1), date(2026, 11, 10), actor_id=ACTOR
    )
    assert changed.is_expired(date(2026, 11, 11))
    with pytest.raises(BusinessRuleViolation):  # 만료 계좌는 늘리는 조정 불가
        await h.service.adjust(h.cohort.id, account_id, 60, "추가", actor_id=ACTOR)
    await h.service.adjust(h.cohort.id, account_id, -60, "만료 정리", actor_id=ACTOR)

    history = await h.service.transactions(h.cohort.id, account_id, before=None, limit=10)
    assert [e.amount for e in history] == [-60, -60, 120]
    user_id = student.user_id
    assert user_id is not None
    assert [a.id for a in await h.service.mine(user_id)] == [account_id]
    mine = await h.service.my_transactions(user_id, account_id, before=None, limit=1)
    assert len(mine) == 1
    with pytest.raises(NotFoundError):
        await h.service.my_transactions(new_id(), account_id, before=None, limit=10)


async def test_team_account_visible_to_members(h: Harness) -> None:
    user_id = new_id()
    student = h.students.add(h.cohort.id, user_id=user_id)
    team = await h.team()
    team.add_member(student.id)
    await h.teams.save(team)
    await h.grant(GrantTarget.TEAMS, team.id)
    (account,) = await h.service.mine(user_id)
    assert account.team_id == team.id
    owners = await h.service.owners_of([account])
    assert list(owners.teams) == [team.id]

"""수강 종료 처리: 팀에서 빼기·1:1 잔여 회수 (A39)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.enrollment_ended import EnrollmentEndedService
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType, MentoringPeriodType
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 11)
COHORT = new_id()


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, **overrides: Any) -> Student:
        values: dict[str, Any] = {
            "cohort_id": COHORT,
            "name": "수강생",
            "hrd_net_status": StudentStatus.TRAINING,
            "enrolled_at": date(2026, 11, 1),
        }
        values.update(overrides)
        student = Student(**values)
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}


def _account(student_id: uuid.UUID, minutes: int) -> BalanceAccount:
    account = BalanceAccount(
        student_id=student_id,
        period_type=MentoringPeriodType.REGULAR_MENTORING,
        valid_from=date(2026, 11, 1),
        valid_until=date(2027, 4, 30),
    )
    if minutes:
        account.grant(minutes, "지급", today=TODAY)
    return account


async def test_removes_members_and_revokes_remaining_idempotently() -> None:
    students = Students()
    active = students.add()
    dropped = students.add(status=EnrollmentStatus.DROPPED)
    removed = students.add(is_removed_in_source=True)
    moved = students.add(status=EnrollmentStatus.TRANSFERRED)
    gone = new_id()  # 명단에서 사라진 수강생
    teams = InMemoryTeamRepository()
    team = MentoringTeam(
        cohort_id=COHORT,
        period_type=MentoringPeriodType.PROJECT_MENTORING,
        team_number=1,
        mentor_id=new_id(),
        member_ids=[active.id, dropped.id, removed.id, gone],
    )
    await teams.add(team)
    accounts = InMemoryBalanceAccountRepository()
    for account in (
        _account(active.id, 120),
        _account(dropped.id, 180),
        _account(moved.id, 60),
        _account(removed.id, 0),  # 잔여 없음
    ):
        await accounts.add(account)
    ledger = InMemoryBalanceLedger()
    audit_logs = InMemoryAuditLogRepository()
    service = EnrollmentEndedService(
        teams=teams,
        accounts=accounts,
        ledger=ledger,
        students=students,
        audit=AuditRecorder(audit_logs, FixedClock(datetime(2026, 11, 11, tzinfo=UTC))),
        uow=FakeUnitOfWork(),
    )

    result = await service.process()
    assert (result.removed_members, result.revoked_accounts, result.revoked_minutes) == (3, 2, 240)
    stored = await teams.get(team.id)
    assert stored is not None
    assert stored.member_ids == [active.id]
    remaining = {a.student_id: a.remaining_minutes for a in accounts.items.values()}
    assert remaining == {active.id: 120, dropped.id: 0, moved.id: 0, removed.id: 0}
    assert {(e.type, e.amount, e.reason) for e in ledger.entries} == {
        (MentoringBalanceTransactionType.STAFF_ADJUST, -180, "수강 종료로 회수"),
        (MentoringBalanceTransactionType.STAFF_ADJUST, -60, "수강 종료로 회수"),
    }
    actions = [log.action for log in audit_logs.logs]
    assert actions.count("mentoring.team.member_auto_remove") == 3
    assert actions.count("mentoring.balance.auto_revoke") == 2
    assert all(log.actor_user_id is None for log in audit_logs.logs)

    again = await service.process()  # 멱등
    assert (again.removed_members, again.revoked_accounts) == (0, 0)


def test_revoke_remaining_ignores_unit_and_expiry() -> None:
    account = _account(new_id(), 120)
    account.held_minutes = 30  # 보류 중인 신청(P11)은 그대로 둔다
    entry = account.revoke_remaining("수강 종료로 회수")
    assert entry is not None
    assert (entry.amount, account.remaining_minutes, account.held_minutes) == (-90, 0, 30)
    assert account.revoke_remaining("다시") is None

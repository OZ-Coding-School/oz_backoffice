"""수강 종료 처리: 팀에서 빼기·대기 신청·1:1 세션 취소·잔여 회수 (A39·A45)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.enrollment_ended import EnrollmentEndedService
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringRequestStatus,
    MentoringSessionStatus,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.mentoring import CleanupStores, InMemoryTeamRepository
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


def _service(
    teams: InMemoryTeamRepository,
    stores: CleanupStores,
    students: "Students",
    audit_logs: InMemoryAuditLogRepository,
    clock: FixedClock,
) -> EnrollmentEndedService:
    return EnrollmentEndedService(
        teams=teams,
        accounts=stores.accounts,
        ledger=stores.ledger,
        requests=stores.requests,
        sessions=stores.sessions,
        cleanup=stores.cleanup,
        students=students,
        audit=AuditRecorder(audit_logs, clock),
        uow=FakeUnitOfWork(),
        clock=clock,
    )


def _account(student_id: uuid.UUID, minutes: int) -> BalanceAccount:
    account = BalanceAccount(
        student_id=student_id,
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
        team_number=1,
        mentor_id=new_id(),
        member_ids=[active.id, dropped.id, removed.id, gone],
    )
    await teams.add(team)
    clock = FixedClock(datetime(2026, 11, 11, tzinfo=UTC))
    audit_logs = InMemoryAuditLogRepository()
    stores = CleanupStores(AuditRecorder(audit_logs, clock), clock)
    accounts = stores.accounts
    for account in (
        _account(active.id, 120),
        _account(dropped.id, 180),
        _account(moved.id, 60),
        _account(removed.id, 0),  # 잔여 없음
    ):
        await accounts.add(account)
    ledger = stores.ledger
    service = _service(teams, stores, students, audit_logs, clock)

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


async def test_cancels_pending_and_upcoming_one_on_one() -> None:
    students = Students()
    active, dropped = students.add(), students.add(status=EnrollmentStatus.DROPPED)
    mentor_id = new_id()
    team = MentoringTeam(
        cohort_id=COHORT, team_number=1, mentor_id=mentor_id, member_ids=[active.id, dropped.id]
    )
    teams = InMemoryTeamRepository()
    await teams.add(team)
    clock = FixedClock(datetime(2026, 11, 11, tzinfo=UTC))
    audit_logs = InMemoryAuditLogRepository()
    stores = CleanupStores(AuditRecorder(audit_logs, clock), clock)
    later = datetime(2026, 11, 20, 5, tzinfo=UTC)

    solo = await stores.pending(mentor_id=mentor_id, requester_id=dropped.id)
    by_leaver = await stores.pending(mentor_id=mentor_id, requester_id=dropped.id, team_id=team.id)
    by_stayer = await stores.pending(
        mentor_id=mentor_id, requester_id=active.id, team_id=team.id, at=later + timedelta(hours=3)
    )
    kept_mine = await stores.pending(mentor_id=mentor_id, requester_id=active.id)

    async def approve(request: Any, at: datetime) -> MentoringSession:
        stored = stores.requests.items[request.id]
        start, end = stored.approve(at, now=clock.now())
        account = (
            await stores.accounts.find_by_owners(
                student_ids=[] if stored.team_id else [stored.requester_id],
                team_ids=[stored.team_id] if stored.team_id else [],
            )
        )[0]
        stores.accounts.items[account.id].use(60, request_id=stored.id, reason="승인")
        session = MentoringSession(
            mentor_id=mentor_id,
            request_id=stored.id,
            starts_at=start,
            ends_at=end,
            title="제목",
            topic="주제",
        )
        await stores.sessions.add(session)
        return session

    future = await approve(
        await stores.pending(
            mentor_id=mentor_id, requester_id=dropped.id, at=later + timedelta(hours=6)
        ),
        later + timedelta(hours=6),
    )
    team_session = await approve(
        await stores.pending(
            mentor_id=mentor_id,
            requester_id=dropped.id,
            team_id=team.id,
            at=later + timedelta(hours=9),
        ),
        later + timedelta(hours=9),
    )

    result = await _service(teams, stores, students, audit_logs, clock).process()
    assert (result.canceled_requests, result.canceled_sessions) == (2, 1)
    assert [stores.status(r) for r in (solo, by_leaver, by_stayer, kept_mine)] == [
        MentoringRequestStatus.CANCELED,
        MentoringRequestStatus.CANCELED,
        MentoringRequestStatus.PENDING,
        MentoringRequestStatus.PENDING,
    ]
    assert stores.sessions.items[future.id].status is MentoringSessionStatus.CANCELED
    assert stores.sessions.items[team_session.id].status is MentoringSessionStatus.SCHEDULED
    (dropped_account,) = await stores.accounts.find_by_owners(student_ids=[dropped.id], team_ids=[])
    stored = stores.accounts.items[dropped_account.id]
    # 대기 보류를 돌려받은 뒤 전부 회수, 취소한 세션은 환불하지 않는다(사용 60분 유지)
    assert (stored.remaining_minutes, stored.held_minutes, stored.used_minutes) == (0, 0, 60)

    again = await _service(teams, stores, students, audit_logs, clock).process()
    assert (again.canceled_requests, again.canceled_sessions, again.revoked_accounts) == (0, 0, 0)

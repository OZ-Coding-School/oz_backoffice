"""수강 종료 처리 (실제 DB): 팀원 제외·잔여 회수·원장·멱등 (A39)."""

from datetime import UTC, datetime

import pytest

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.application.student_queries import StudentQueries
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.mentoring.application.balance_service import BalanceService, GrantTarget
from app.contexts.mentoring.application.enrollment_ended import EnrollmentEndedService
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.clock import FixedClock
from app.core.uow import UnitOfWork
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user

pytestmark = pytest.mark.integration

CLOCK = FixedClock(datetime(2026, 11, 11, 3, tzinfo=UTC))


async def test_process_on_real_db() -> None:
    cohort = await create_cohort()
    repo = TortoiseStudentRepository()
    active = make_student(cohort_id=cohort.id)
    dropped = make_student(cohort_id=cohort.id)
    for s in (active, dropped):
        await repo.add(s)
    teams = TortoiseMentoringTeamRepository()
    team = MentoringTeam(
        cohort_id=cohort.id,
        team_number=1,
        mentor_id=(await create_mentor()).id,
        member_ids=[active.id, dropped.id],
    )
    await teams.add(team)
    accounts = TortoiseBalanceAccountRepository()
    ledger = TortoiseBalanceTransactionRepository()
    audit = AuditRecorder(TortoiseAuditLogRepository(), CLOCK)
    students = StudentQueries(repo)
    await BalanceService(
        accounts=accounts,
        ledger=ledger,
        teams=teams,
        settings=TortoiseCohortMentoringSettingsRepository(),
        students=students,
        cohorts=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        audit=audit,
        uow=UnitOfWork(),
        clock=CLOCK,
    ).grant(
        cohort.id,
        target=GrantTarget.ALL_STUDENTS,
        ids=[],
        minutes=120,
        valid_from=None,
        valid_until=None,
        reason="지급",
        actor_id=(await create_user()).id,
    )

    dropped.status = EnrollmentStatus.DROPPED  # 동기화가 상태를 바꿨다고 가정
    await repo.save(dropped)

    service = EnrollmentEndedService(
        teams=teams,
        accounts=accounts,
        ledger=ledger,
        students=students,
        audit=audit,
        uow=UnitOfWork(),
    )
    result = await service.process()
    assert (result.removed_members, result.revoked_accounts, result.revoked_minutes) == (1, 1, 120)
    stored = await teams.get(team.id)
    assert stored is not None
    assert stored.member_ids == [active.id]
    (left,) = await accounts.find_by_owners(student_ids=[dropped.id], team_ids=[])
    assert left.remaining_minutes == 0
    history = await ledger.list_by_account(left.id, before=None, limit=5)
    assert [(e.amount, e.reason) for e in history] == [(-120, "수강 종료로 회수"), (120, "지급")]
    assert (await service.process()).revoked_accounts == 0

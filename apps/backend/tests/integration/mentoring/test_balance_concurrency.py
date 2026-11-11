"""동시 조정 경합: 계좌 행 잠금으로 잔여가 음수가 되지 않는다 (A39)."""

import asyncio
from datetime import UTC, datetime

import pytest

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.application.student_queries import StudentQueries
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.mentoring.application.balance_service import BalanceService, GrantTarget
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.clock import FixedClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_user

pytestmark = pytest.mark.integration


def _service() -> BalanceService:
    clock = FixedClock(datetime(2026, 11, 11, 3, tzinfo=UTC))
    return BalanceService(
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        teams=TortoiseMentoringTeamRepository(),
        settings=TortoiseCohortMentoringSettingsRepository(),
        students=StudentQueries(TortoiseStudentRepository()),
        cohorts=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


async def test_concurrent_adjustments_never_go_negative() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    actor = (await create_user()).id
    result = await _service().grant(
        cohort.id,
        target=GrantTarget.STUDENTS,
        ids=[student.id],
        minutes=60,
        valid_from=None,
        valid_until=None,
        reason="지급",
        actor_id=actor,
    )
    account_id = result.granted[0].account_id

    async def take() -> str:
        try:
            await _service().adjust(cohort.id, account_id, -60, "차감", actor_id=actor)
        except BusinessRuleViolation as error:
            return error.code
        return "ok"

    outcomes = await asyncio.gather(take(), take())
    assert sorted(outcomes) == ["insufficient_balance", "ok"]
    (account,) = await TortoiseBalanceAccountRepository().lock_many([account_id])
    assert account.remaining_minutes == 0

"""시간 계좌·원장 저장과 DB 제약 (부분 유니크·check)."""

from datetime import date

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseMentoringTeamRepository,
)
from app.shared.errors import ConflictError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

accounts = TortoiseBalanceAccountRepository()
ledger = TortoiseBalanceTransactionRepository()
REGULAR = MentoringPeriodType.REGULAR_MENTORING
PROJECT = MentoringPeriodType.PROJECT_MENTORING
TODAY = date(2026, 11, 11)


def _account(**owner: object) -> BalanceAccount:
    return BalanceAccount(
        period_type=owner.pop("period_type", REGULAR),  # type: ignore[arg-type]
        valid_from=date(2026, 11, 1),
        valid_until=date(2027, 4, 30),
        **owner,  # type: ignore[arg-type]
    )


async def test_accounts_ledger_and_constraints() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    team = MentoringTeam(
        cohort_id=cohort.id,
        period_type=PROJECT,
        team_number=1,
        mentor_id=(await create_mentor()).id,
    )
    await TortoiseMentoringTeamRepository().add(team)

    account = _account(student_id=student.id)
    entries = [account.grant(180, "기본 지급", today=TODAY)]
    await accounts.add(account)
    entries.append(account.adjust(-60, "정정", today=TODAY))
    await accounts.save(account)
    await ledger.add_many(entries)
    team_account = _account(team_id=team.id, period_type=PROJECT)
    await accounts.add(team_account)

    (locked,) = await accounts.lock_many([account.id])
    assert (locked.total_minutes, locked.remaining_minutes) == (120, 120)
    history = await ledger.list_by_account(account.id, before=None, limit=10)
    assert [(e.amount, e.after_remaining) for e in history] == [(-60, 120), (180, 180)]
    older = await ledger.list_by_account(account.id, before=history[0].id, limit=10)
    assert [e.amount for e in older] == [180]

    found = await accounts.find_by_owners(
        student_ids=[student.id], team_ids=[team.id], period_type=None
    )
    assert {a.id for a in found} == {account.id, team_account.id}
    page, total = await accounts.list_page(
        cohort.id, period_type=None, owner=None, limit=10, offset=0
    )
    assert total == 2
    assert {a.id for a in page} == {account.id, team_account.id}
    teams_only, _ = await accounts.list_page(
        cohort.id, period_type=None, owner="TEAM", limit=10, offset=0
    )
    assert [a.id for a in teams_only] == [team_account.id]
    other, other_total = await accounts.list_page(
        new_id(), period_type=None, owner=None, limit=10, offset=0
    )
    assert (other, other_total) == ([], 0)

    with pytest.raises(ConflictError):  # (수강생, 유형)당 하나
        await accounts.add(_account(student_id=student.id))
    await accounts.add(_account(student_id=student.id, period_type=PROJECT))

    db = connections.get("default")
    for sql in (
        "remaining_minutes = remaining_minutes + 60",  # 잔여 = 합계 − 보류 − 사용
        "total_minutes = -60, remaining_minutes = -60",
        "valid_until = '2026-10-01'",
        "team_id = '" + str(team.id) + "'",  # 소유자 둘
    ):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_balance_accounts SET {sql} WHERE id = $1", [str(account.id)]
            )
    for sql in ("amount = -60", "request_id = '" + str(new_id()) + "'", "type = 'BONUS'"):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_balance_transactions SET {sql} WHERE id = $1",
                [str(history[1].id)],
            )

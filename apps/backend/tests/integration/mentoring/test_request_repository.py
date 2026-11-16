"""멘토링 신청 저장과 DB 제약 (A42)."""

from datetime import date, datetime, timedelta

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringRequestStatus,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringTeamRepository,
)
from app.shared.ids import new_id
from app.shared.time import KST
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

repo = TortoiseMentoringRequestRepository()
T = datetime(2026, 11, 20, 14, tzinfo=KST)


async def test_request_round_trip_queries_and_constraints() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    other = make_student(cohort_id=(await create_cohort()).id)
    for s in (student, other):
        await TortoiseStudentRepository().add(s)
    mentor = await create_mentor()
    team = MentoringTeam(cohort_id=cohort.id, team_number=1, mentor_id=mentor.id)
    await TortoiseMentoringTeamRepository().add(team)

    def make(**overrides: object) -> MentoringRequest:
        values: dict[str, object] = {
            "requester_id": student.id,
            "mentor_id": mentor.id,
            "topic": "리뷰",
            "detail": "내용",
            "desired_times": [T, T + timedelta(days=1)],
            "duration": 60,
        }
        values.update(overrides)
        return MentoringRequest(**values)  # type: ignore[arg-type]

    solo = make()
    await repo.add(solo)
    team_request = make(team_id=team.id, desired_times=[T + timedelta(hours=3)])
    await repo.add(team_request)
    elsewhere = make(requester_id=other.id)
    await repo.add(elsewhere)

    loaded = await repo.get(solo.id)
    assert loaded is not None
    assert loaded.desired_times == [T, T + timedelta(days=1)]
    assert await repo.count_pending(requester_id=student.id) == 1  # 팀 신청은 따로 센다
    assert await repo.count_pending(team_id=team.id) == 1

    mine, total = await repo.list_for_participants(
        student_ids=[student.id], team_ids=[team.id], status=None, limit=10, offset=0
    )
    assert total == 2
    assert {r.id for r in mine} == {solo.id, team_request.id}
    by_cohort, cohort_total = await repo.list_by_cohort(
        cohort.id, status=MentoringRequestStatus.PENDING, mentor_id=mentor.id, limit=10, offset=0
    )
    assert cohort_total == 2
    assert elsewhere.id not in {r.id for r in by_cohort}
    # 신청자 필터는 1:1만, 팀 필터는 그 팀만 (팀 신청의 신청자도 같은 수강생이다, A59)
    for filters, expected in (
        ({"student_id": student.id}, [solo.id]),
        ({"team_id": team.id}, [team_request.id]),
        ({"student_id": student.id, "team_id": team.id}, []),
        ({"student_id": other.id}, []),  # 다른 기수
    ):
        found, found_total = await repo.list_by_cohort(
            cohort.id, status=None, mentor_id=None, limit=10, offset=0, **filters
        )
        assert ([r.id for r in found], found_total) == (expected, len(expected))
    _, mentor_total = await repo.list_for_mentor(mentor.id, status=None, limit=10, offset=0)
    assert mentor_total == 3

    assert {r.id for r in await repo.list_stale(T + timedelta(hours=4))} == {team_request.id}
    assert len(await repo.list_stale(T + timedelta(days=2))) == 3

    locked = await repo.lock(solo.id)
    assert locked is not None
    locked.cancel("일정 변경", now=T)
    await repo.save(locked)
    assert await repo.count_pending(requester_id=student.id) == 0

    db = connections.get("default")
    for sql in (
        "status = 'CANCELED', canceled_at = NULL",  # 취소 시각 없음
        "cancel_reason = NULL",  # 취소 사유 필수
        "duration = 150",
        "duration = 45",
        "detail = ''",
        "replaced_request_id = '" + str(new_id()) + "'",  # 없는 신청
    ):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_requests SET {sql} WHERE id = $1", [str(solo.id)]
            )
    account = BalanceAccount(
        student_id=student.id, valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
    )
    await TortoiseBalanceAccountRepository().add(account)
    hold = BalanceTransaction(
        account_id=account.id,
        type=MentoringBalanceTransactionType.HOLD,
        amount=60,
        after_remaining=0,
        after_held=60,
        reason="신청",
        request_id=new_id(),  # 없는 신청
    )
    with pytest.raises(IntegrityError):  # 원장 request_id → 신청 FK
        await TortoiseBalanceTransactionRepository().add_many([hold])


async def test_overtime_ledger_type_is_allowed_once_per_request() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    request = MentoringRequest(
        requester_id=student.id,
        mentor_id=mentor.id,
        topic="리뷰",
        detail="내용",
        desired_times=[T],
        duration=60,
    )
    await repo.add(request)
    account = BalanceAccount(
        student_id=student.id, valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
    )
    await TortoiseBalanceAccountRepository().add(account)
    ledger = TortoiseBalanceTransactionRepository()

    def overtime() -> BalanceTransaction:
        return BalanceTransaction(
            account_id=account.id,
            type=MentoringBalanceTransactionType.OVERTIME,
            amount=30,
            after_remaining=0,
            after_held=0,
            reason="초과 진행",
            request_id=request.id,
        )

    await ledger.add_many([overtime()])
    with pytest.raises(IntegrityError):  # 신청당 하나
        await ledger.add_many([overtime()])

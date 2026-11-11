"""수강 종료 처리 (decisions A39).

명단 동기화가 끝난 뒤 작업으로 실행한다. 수강 중이 아닌 수강생(수료·조기취업·중도포기·기수 이동·
원천 삭제)을
- 모든 팀에서 빼고,
- 1:1 계좌의 잔여를 모두 회수한다(STAFF_ADJUST −, 사유 '수강 종료로 회수').
대기 신청 취소·보류 시간 회수는 P11에서 붙인다. 다시 수강 중이 돼도 자동으로 되돌리지 않는다.
멱등이라 여러 번 실행해도 같은 결과다(이미 뺀 팀원·잔여 0인 계좌는 대상이 아님).
처리자는 시스템(actor 없음)으로 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.domain.balance import BalanceTransaction
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    MentoringTeamRepository,
)
from app.core.uow import UnitOfWork

REVOKE_REASON = "수강 종료로 회수"


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...


@dataclass(frozen=True, slots=True)
class EnrollmentEndedResult:
    removed_members: int
    revoked_accounts: int
    revoked_minutes: int


def _ended(student: Student | None) -> bool:
    """명단에서 사라졌거나 수강 중이 아니면 종료로 본다."""
    return student is None or not student.is_enrolled or student.is_removed_in_source


class EnrollmentEndedService:
    def __init__(
        self,
        *,
        teams: MentoringTeamRepository,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        students: StudentLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._teams = teams
        self._accounts = accounts
        self._ledger = ledger
        self._students = students
        self._audit = audit
        self._uow = uow

    async def process(self) -> EnrollmentEndedResult:
        async with self._uow:
            memberships = await self._teams.list_memberships()
            candidates = await self._accounts.list_student_accounts_with_remaining()
            student_ids = list(
                {s for _, s in memberships}
                | {a.student_id for a in candidates if a.student_id is not None}
            )
            students = await self._students.get_many(student_ids)

            leaving = [(t, s) for t, s in memberships if _ended(students.get(s))]
            await self._teams.remove_memberships(leaving)
            for team_id, student_id in leaving:
                await self._audit.record(
                    actor_user_id=None,
                    action="mentoring.team.member_auto_remove",
                    target_type="mentoring_team",
                    target_id=team_id,
                    before={"student_id": str(student_id)},
                )

            ended_ids = [
                a.id
                for a in candidates
                if a.student_id is not None and _ended(students.get(a.student_id))
            ]
            entries: list[BalanceTransaction] = []
            revoked = 0
            for account in await self._accounts.lock_many(ended_ids):
                entry = account.revoke_remaining(REVOKE_REASON)
                if entry is None:  # 잠그는 사이 잔여가 0이 됐다
                    continue
                entries.append(entry)
                revoked -= entry.amount
                await self._accounts.save(account)
                await self._audit.record(
                    actor_user_id=None,
                    action="mentoring.balance.auto_revoke",
                    target_type="mentoring_balance_account",
                    target_id=account.id,
                    after={"amount": entry.amount, "reason": REVOKE_REASON},
                )
            await self._ledger.add_many(entries)
        return EnrollmentEndedResult(
            removed_members=len(leaving), revoked_accounts=len(entries), revoked_minutes=revoked
        )

"""수강 종료 처리 (decisions A39·A42·A45).

명단 동기화가 끝난 뒤 작업으로 실행한다. 수강 중이 아닌 수강생(수료·조기취업·중도포기·기수 이동·
원천 삭제)을
- 모든 팀에서 빼고, 그 사람이 신청한 그 팀의 대기 신청을 취소한다(팀 계좌로 RELEASE),
- 1:1 대기 신청을 취소하고(RELEASE),
- 아직 시작 전인 1:1 예정 세션을 환불 없이 취소한다(팀 세션은 유지),
- 1:1 계좌의 잔여(돌려받은 보류 포함)를 모두 회수한다(STAFF_ADJUST −, 사유 '수강 종료로 회수').
다시 수강 중이 돼도 자동으로 되돌리지 않는다.
멱등이라 여러 번 실행해도 같은 결과다(이미 뺀 팀원·잔여 0인 계좌는 대상이 아님).
처리자는 시스템(actor 없음)으로 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.request_cleanup import (
    ENROLLMENT_ENDED,
    LEFT_TEAM,
    RequestCleanup,
)
from app.contexts.mentoring.domain.balance import BalanceTransaction
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.core.clock import Clock
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
    canceled_requests: int = 0
    canceled_sessions: int = 0


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
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
        cleanup: RequestCleanup,
        students: StudentLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._teams = teams
        self._accounts = accounts
        self._ledger = ledger
        self._requests = requests
        self._sessions = sessions
        self._cleanup = cleanup
        self._students = students
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def process(self) -> EnrollmentEndedResult:
        async with self._uow:
            now = self._clock.now()
            memberships = await self._teams.list_memberships()
            pending = await self._requests.list_pending(solo=True)
            upcoming = await self._sessions.list_upcoming(now, solo=True)
            upcoming_requests = await self._requests.get_many([s.request_id for s in upcoming])
            candidates = await self._accounts.list_student_accounts_with_remaining()
            student_ids = list(
                {s for _, s in memberships}
                | {r.requester_id for r in pending}
                | {r.requester_id for r in upcoming_requests.values()}
                | {a.student_id for a in candidates if a.student_id is not None}
            )
            students = await self._students.get_many(student_ids)

            def ended(student_id: uuid.UUID) -> bool:
                return _ended(students.get(student_id))

            leaving = [(t, s) for t, s in memberships if ended(s)]
            await self._teams.remove_memberships(leaving)
            for team_id, student_id in leaving:
                await self._audit.record(
                    actor_user_id=None,
                    action="mentoring.team.member_auto_remove",
                    target_type="mentoring_team",
                    target_id=team_id,
                    before={"student_id": str(student_id)},
                )
            canceled = 0
            if leaving:
                pairs = set(leaving)
                team_pending = await self._requests.list_pending(
                    team_ids=list({t for t, _ in leaving}),
                    requester_ids=list({s for _, s in leaving}),
                )
                canceled += await self._cleanup.cancel_pending(
                    [r for r in team_pending if (r.team_id, r.requester_id) in pairs],
                    LEFT_TEAM,
                    actor_id=None,
                )
            ended_pending = [r for r in pending if ended(r.requester_id)]
            canceled += await self._cleanup.cancel_pending(
                ended_pending, ENROLLMENT_ENDED, actor_id=None
            )
            sessions = await self._cleanup.cancel_sessions(
                [s for s in upcoming if ended(upcoming_requests[s.request_id].requester_id)],
                ENROLLMENT_ENDED,
                refund=False,
                actor_id=None,
            )

            # 돌려받은 보류까지 포함해 회수한다 (잔여가 0이던 계좌도 대기 신청이 있었으면 대상)
            ended_students = {
                a.student_id for a in candidates if a.student_id and ended(a.student_id)
            } | {r.requester_id for r in ended_pending}
            owned = await self._accounts.find_by_owners(
                student_ids=list(ended_students), team_ids=[]
            )
            entries: list[BalanceTransaction] = []
            revoked = 0
            for account in await self._accounts.lock_many([a.id for a in owned]):
                entry = account.revoke_remaining(REVOKE_REASON)
                if entry is None:  # 잔여가 없다
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
            removed_members=len(leaving),
            revoked_accounts=len(entries),
            revoked_minutes=revoked,
            canceled_requests=canceled,
            canceled_sessions=sessions,
        )

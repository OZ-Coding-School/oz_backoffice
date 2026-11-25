"""멘티 목록 (운영진 멘티 관리, decisions A59).

기수 명단의 수강생마다 소속 팀, 1:1 시간 계좌, 1:1 대기 신청 수, 1:1 세션 수(예정·완료)를
묶어 보여 준다. 팀 신청·세션과 팀 계좌는 팀 관리에서 본다.
"""

import builtins
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.team import MentoringTeam

UPCOMING = (MentoringSessionStatus.SCHEDULED, MentoringSessionStatus.IN_PROGRESS)


class CohortRoster(Protocol):
    """academy `StudentQueries`."""

    async def in_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        statuses: Collection[EnrollmentStatus] | None,
        name: str | None,
    ) -> list[Student]: ...


@dataclass(frozen=True, kw_only=True)
class MenteeSummary:
    student: Student
    team: MentoringTeam | None
    account: BalanceAccount | None
    pending_requests: int
    upcoming_sessions: int
    completed_sessions: int


class MenteeQueries:
    def __init__(
        self,
        *,
        roster: CohortRoster,
        teams: MentoringTeamRepository,
        accounts: BalanceAccountRepository,
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
    ) -> None:
        self._roster = roster
        self._teams = teams
        self._accounts = accounts
        self._requests = requests
        self._sessions = sessions

    async def list(
        self,
        cohort_id: uuid.UUID,
        *,
        statuses: Collection[EnrollmentStatus] | None,
        name: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MenteeSummary], int]:
        """명단은 이름순으로 자르고, 계좌·팀·건수는 그 페이지의 수강생만 묶어 읽는다."""
        students = await self._roster.in_cohort(cohort_id, statuses=statuses, name=name)
        page = students[offset : offset + limit]
        return await self.summarize(page), len(students)

    async def of_student(self, student: Student) -> MenteeSummary:
        """한 수강생의 팀·1:1 계좌·건수 (수강생 상세 A99)."""
        return (await self.summarize([student]))[0]

    async def summarize(self, page: Sequence[Student]) -> builtins.list[MenteeSummary]:
        ids = [s.id for s in page]
        if not ids:
            return []
        team_of = await self._teams.team_of_students(ids)
        teams = {t.id: t for t in await self._teams.list_by_ids(sorted(set(team_of.values())))}
        accounts = {
            a.student_id: a
            for a in await self._accounts.find_by_owners(student_ids=ids, team_ids=[])
        }
        pending = await self._requests.count_pending_by_requesters(ids)
        sessions = await self._sessions.count_by_requesters(ids)
        items: builtins.list[MenteeSummary] = []
        for s in page:
            by_status = sessions.get(s.id, {})
            team_id = team_of.get(s.id)
            items.append(
                MenteeSummary(
                    student=s,
                    team=teams.get(team_id) if team_id else None,
                    account=accounts.get(s.id),
                    pending_requests=pending.get(s.id, 0),
                    upcoming_sessions=sum(by_status.get(st, 0) for st in UPCOMING),
                    completed_sessions=by_status.get(MentoringSessionStatus.COMPLETED, 0),
                )
            )
        return items

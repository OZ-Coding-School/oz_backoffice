"""팀 관리 목록의 팀 계좌·건수 (운영진 팀 관리, decisions A108).

팀마다 팀 시간 계좌, 대기 신청 수, 세션 수(예정·진행 중 / 완료)를 묶어 읽는다.
"""

import uuid
from dataclasses import dataclass

from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
)

UPCOMING = (MentoringSessionStatus.SCHEDULED, MentoringSessionStatus.IN_PROGRESS)


@dataclass(frozen=True, kw_only=True)
class TeamStats:
    account: BalanceAccount | None
    pending_requests: int
    upcoming_sessions: int
    completed_sessions: int


class TeamStatsQueries:
    def __init__(
        self,
        *,
        accounts: BalanceAccountRepository,
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
    ) -> None:
        self._accounts = accounts
        self._requests = requests
        self._sessions = sessions

    async def of(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, TeamStats]:
        if not team_ids:
            return {}
        accounts = {
            a.team_id: a
            for a in await self._accounts.find_by_owners(student_ids=[], team_ids=team_ids)
        }
        pending = await self._requests.count_pending_by_teams(team_ids)
        sessions = await self._sessions.count_by_teams(team_ids)
        result: dict[uuid.UUID, TeamStats] = {}
        for team_id in team_ids:
            by_status = sessions.get(team_id, {})
            result[team_id] = TeamStats(
                account=accounts.get(team_id),
                pending_requests=pending.get(team_id, 0),
                upcoming_sessions=sum(by_status.get(st, 0) for st in UPCOMING),
                completed_sessions=by_status.get(MentoringSessionStatus.COMPLETED, 0),
            )
        return result

"""멘토링 신청 승인·반려 (decisions M3·M9·A42·A43).

승인 (그 신청의 멘토만):
- 희망 일시 중 하나를 고르고, 고른 일시가 시작하기 전이어야 한다(신청 마감·운영시간·불가 시간은 다시
  보지 않는다, A43).
- 신청자 일정이 겹치면 409 `participant_schedule_conflict`: 1:1은 그 수강생의 1:1 세션과 소속 팀
  세션, 팀은 그 팀의 세션과 팀원 각자의 1:1 세션 (취소 제외).
- 멘토 일정이 겹치면 DB EXCLUDE가 막는다 → 409 `mentor_schedule_conflict`.
- 보류를 사용으로 옮기고(USING) 세션(SCHEDULED)을 만든다. 제목은 자동(회차 = 같은 신청자·같은 멘토의
  취소되지 않은 세션 순서).
- 커밋 후 Meet 공간 생성을 워커로 보낸다(A48).
반려 (그 신청의 멘토만, 대기 중, 사유 필수): 보류 해제(RELEASE).

잠금: 참여자(신청자·팀원·팀)의 계좌를 id 순서로 잠근 뒤 신청을 잠근다(계좌 → 신청 → 세션). 같은
참여자의 승인끼리 직렬화돼 신청자 겹침 검사가 경합에 빠지지 않는다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.meet_service import MeetSpaceScheduler
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession, session_title
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError, NotFoundError, PermissionDeniedError

TARGET = "mentoring_request"
USING_REASON = "멘토링 승인"
REJECT_REASON = "신청 반려"


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


class UserLookup(Protocol):
    """identity `UserQueries`."""

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]: ...


@dataclass(frozen=True, slots=True)
class Participants:
    """신청자 일정 겹침을 볼 대상: 1:1 세션은 수강생으로, 팀 세션은 팀으로 찾는다."""

    student_ids: list[uuid.UUID]
    team_ids: list[uuid.UUID]
    label: str  # 세션 제목의 신청자 (팀 이름 또는 수강생 이름)


class MentoringApprovalService:
    def __init__(
        self,
        *,
        requests: MentoringRequestRepository,
        sessions: MentoringSessionRepository,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        teams: MentoringTeamRepository,
        students: StudentLookup,
        mentors: MentorLookup,
        users: UserLookup,
        meet: MeetSpaceScheduler,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._requests = requests
        self._sessions = sessions
        self._accounts = accounts
        self._ledger = ledger
        self._teams = teams
        self._students = students
        self._mentors = mentors
        self._users = users
        self._meet = meet
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def approve(
        self, user_id: uuid.UUID, request_id: uuid.UUID, starts_at: datetime
    ) -> tuple[MentoringRequest, MentoringSession]:
        mentor, request = await self._mentor_request(user_id, request_id)
        who = await self._participants(request)
        mentor_label = await self._mentor_label(mentor)
        found = await self._accounts.find_by_owners(
            student_ids=who.student_ids, team_ids=who.team_ids
        )
        async with self._uow:
            accounts = await self._accounts.lock_many([a.id for a in found])
            request = await self._lock(request_id)
            account = self._account_of(request, accounts)
            start, end = request.approve(starts_at, now=self._clock.now())
            if await self._sessions.has_participant_overlap(
                student_ids=who.student_ids, team_ids=who.team_ids, starts_at=start, ends_at=end
            ):
                raise ConflictError(
                    "신청자의 다른 멘토링 일정과 겹칩니다.", code="participant_schedule_conflict"
                )
            number = 1 + await self._sessions.count_for_pair(
                mentor.id,
                requester_id=None if request.team_id else request.requester_id,
                team_id=request.team_id,
            )
            session = MentoringSession(
                mentor_id=mentor.id,
                request_id=request.id,
                starts_at=start,
                ends_at=end,
                title=session_title(who.label, mentor_label, number),
                topic=request.topic,
            )
            entry = account.use(request.duration, request_id=request.id, reason=USING_REASON)
            await self._sessions.add(session)
            await self._requests.save(request)
            await self._accounts.save(account)
            await self._ledger.add_many([entry])
            await self._record(user_id, "approve", request, session)
            session_id = session.id
            self._uow.on_commit(lambda: self._meet.space_needed(session_id))
        return request, session

    async def reject(
        self, user_id: uuid.UUID, request_id: uuid.UUID, reason: str
    ) -> MentoringRequest:
        _, request = await self._mentor_request(user_id, request_id)
        found = await self._accounts.find_by_owners(
            student_ids=[] if request.team_id else [request.requester_id],
            team_ids=[request.team_id] if request.team_id else [],
        )
        async with self._uow:
            accounts = await self._accounts.lock_many([a.id for a in found])
            request = await self._lock(request_id)
            account = self._account_of(request, accounts)
            request.reject(reason, now=self._clock.now())
            entry = account.release(request.duration, request_id=request.id, reason=REJECT_REASON)
            await self._requests.save(request)
            await self._accounts.save(account)
            await self._ledger.add_many([entry])
            await self._record(user_id, "reject", request)
        return request

    # ------------------------------------------------------------------ 내부
    async def _mentor_request(
        self, user_id: uuid.UUID, request_id: uuid.UUID
    ) -> tuple[Mentor, MentoringRequest]:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        request = await self._requests.get(request_id)
        if request is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        if request.mentor_id != mentor.id:
            raise PermissionDeniedError(
                "본인에게 온 신청만 처리할 수 있습니다.", code="not_request_mentor"
            )
        return mentor, request

    async def _participants(self, request: MentoringRequest) -> Participants:
        if request.team_id is not None:
            team = await self._teams.get(request.team_id)
            if team is None:
                raise NotFoundError("팀을 찾을 수 없습니다.", code="team_not_found")
            return Participants(
                student_ids=list(team.member_ids), team_ids=[team.id], label=team.label
            )
        student = (await self._students.get_many([request.requester_id])).get(request.requester_id)
        teams = await self._teams.team_of_students([request.requester_id])
        return Participants(
            student_ids=[request.requester_id],
            team_ids=list(teams.values()),
            label=student.name if student else "수강생",
        )

    async def _mentor_label(self, mentor: Mentor) -> str:
        user = (await self._users.get_many([mentor.user_id])).get(mentor.user_id)
        return mentor.display_name(user.name if user else "멘토")

    async def _lock(self, request_id: uuid.UUID) -> MentoringRequest:
        request = await self._requests.lock(request_id)
        if request is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        return request

    @staticmethod
    def _account_of(request: MentoringRequest, accounts: list[BalanceAccount]) -> BalanceAccount:
        for account in accounts:
            if request.team_id is not None and account.team_id == request.team_id:
                return account
            if request.team_id is None and account.student_id == request.requester_id:
                return account
        raise NotFoundError("신청의 시간 계좌를 찾을 수 없습니다.", code="balance_account_missing")

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        request: MentoringRequest,
        session: MentoringSession | None = None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.request.{action}",
            target_type=TARGET,
            target_id=request.id,
            after={
                "status": request.status.value,
                "session_id": str(session.id) if session else None,
                "starts_at": session.starts_at.isoformat() if session else None,
                "reject_reason": request.reject_reason,
            },
        )

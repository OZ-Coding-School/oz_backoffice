"""멘토링 신청·승인 전 취소·대기 만료·조회 (decisions M1·M5·M9·A41·A42).

신청 (수강생 본인, 대리 신청 없음):
- 1:1은 기수·멘토를 고른다(그 기수 활성 배정 멘토).
- 팀은 팀을 고르면 팀 담당 멘토에게 간다(팀원 누구나).
- 신청자는 그 기수 수강 중이어야 하고, 기수 설정에서 1:1·팀 멘토링이 허용돼 있어야 한다.
- 신청 시간은 진행 단위의 배수(최대 120분).
- 희망 일시는 각각 멘토의 신청 가능 구간(P9 계산) 안이어야 한다.
- 계좌(1:1은 수강생, 팀은 팀)가 있어야 하고, 사용 기간 안의 날짜여야 하며, 대기 신청 수가 기수 설정
  (`max_pending_requests`, 1:1 수강생당·팀 팀당)보다 적어야 한다. 신청 시간만큼 보류(HOLD)한다.
취소(승인 전): 신청자만, 사유 필수 → 보류 해제(RELEASE). 승인 후 취소·운영진 취소는 P11-3.
대기 만료: 승인 가능한 희망 일시(시작 전)가 남지 않은 대기 신청을 주기 작업이 취소하고 RELEASE.
계좌 → 신청 순서로 잠근다. 모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.availability_service import AvailableTimes
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    CohortMentoringSettingsRepository,
    MentoringRequestRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.request import EXPIRED_REASON, MentoringRequest
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.time import business_date

TARGET = "mentoring_request"
HOLD_REASON = "멘토링 신청"
RELEASE_REASON = "신청 취소"


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...
    async def of_user(self, user_id: uuid.UUID) -> list[Student]: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


class AvailableTimesLookup(Protocol):
    """mentoring `AvailableTimesService`."""

    async def times_for(
        self, mentor_id: uuid.UUID, cohort_id: uuid.UUID, start: date, end: date
    ) -> AvailableTimes: ...


@dataclass(frozen=True, slots=True)
class RequestInput:
    topic: str
    detail: str
    desired_times: list[datetime]
    duration: int
    cohort_id: uuid.UUID | None = None  # 1:1
    mentor_id: uuid.UUID | None = None  # 1:1
    team_id: uuid.UUID | None = None  # 팀


def _active(student: Student) -> bool:
    return student.is_enrolled and not student.is_removed_in_source


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


class MentoringRequestService:
    def __init__(
        self,
        *,
        requests: MentoringRequestRepository,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        teams: MentoringTeamRepository,
        settings: CohortMentoringSettingsRepository,
        students: StudentLookup,
        mentors: MentorLookup,
        availability: AvailableTimesLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._requests = requests
        self._accounts = accounts
        self._ledger = ledger
        self._teams = teams
        self._settings = settings
        self._students = students
        self._mentors = mentors
        self._availability = availability
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 신청
    async def create(self, user_id: uuid.UUID, data: RequestInput) -> MentoringRequest:
        requester, cohort_id, mentor_id, team_id = await self._resolve(user_id, data)
        settings = await self._settings.get_by_cohort(cohort_id)
        if settings is None:
            raise NotFoundError(
                "이 기수의 멘토링 설정이 아직 없습니다.", code="mentoring_settings_not_configured"
            )
        _rule(
            settings.allow_team_mentoring if team_id else settings.allow_1_on_1,
            "이 기수에서 허용하지 않는 멘토링 방식입니다.",
            "mentoring_mode_not_allowed",
        )
        request = MentoringRequest(
            requester_id=requester.id,
            mentor_id=mentor_id,
            team_id=team_id,
            topic=data.topic,
            detail=data.detail,
            desired_times=data.desired_times,
            duration=data.duration,
        )
        request.ensure_duration_unit(settings.allowed_duration)
        await self._ensure_available(request, cohort_id)
        days = [business_date(start) for start, _ in request.slots()]

        async with self._uow:
            account = await self._locked_account(request)
            if account is None:
                raise BusinessRuleViolation(
                    "지급된 멘토링 시간이 없습니다.", code="balance_account_missing"
                )
            _rule(
                all(account.valid_from <= d <= account.valid_until for d in days),
                "희망 일시가 멘토링 시간 사용 기간 밖입니다.",
                "desired_time_outside_validity",
            )
            pending = await self._requests.count_pending(
                requester_id=None if team_id else requester.id, team_id=team_id
            )
            _rule(
                pending < settings.max_pending_requests,
                f"대기 중인 신청은 {settings.max_pending_requests}건까지입니다.",
                "too_many_pending_requests",
            )
            entry = account.hold(request.duration, request_id=request.id, reason=HOLD_REASON)
            await self._requests.add(request)
            await self._accounts.save(account)
            await self._ledger.add_many([entry])
            await self._record(user_id, "create", request)
        return request

    # ------------------------------------------------------------------ 취소·만료
    async def cancel(
        self, user_id: uuid.UUID, request_id: uuid.UUID, reason: str
    ) -> MentoringRequest:
        """승인 전 취소 (신청자만, A42)."""
        request = await self._get(request_id)
        requester = (await self._students.get_many([request.requester_id])).get(
            request.requester_id
        )
        if requester is None or requester.user_id != user_id:
            raise PermissionDeniedError("신청한 사람만 취소할 수 있습니다.", code="not_requester")
        async with self._uow:
            account, request = await self._lock_pair(request)
            entry = self._cancel(request, account, reason)
            await self._persist(request, account, entry)
            await self._record(user_id, "cancel", request)
        return request

    async def expire_stale(self) -> int:
        """승인 가능한 희망 일시가 없는 대기 신청을 취소한다 (주기 작업, 멱등)."""
        now = self._clock.now()
        expired = 0
        for stale in await self._requests.list_stale(now):
            async with self._uow:
                account, request = await self._lock_pair(stale)
                if not request.is_stale(now):  # 잠그는 사이 처리됐다
                    continue
                entry = self._cancel(request, account, EXPIRED_REASON)
                await self._persist(request, account, entry)
                await self._record(None, "expire", request)
                expired += 1
        return expired

    # ------------------------------------------------------------------ 조회
    async def list_mine(
        self, user_id: uuid.UUID, *, status: MentoringRequestStatus | None, limit: int, offset: int
    ) -> tuple[list[MentoringRequest], int]:
        """본인 1:1 신청과 소속 팀의 신청 (팀원 모두 조회, A42)."""
        registrations = await self._students.of_user(user_id)
        teams = await self._teams.list_by_students([s.id for s in registrations])
        return await self._requests.list_for_participants(
            student_ids=[s.id for s in registrations],
            team_ids=[t.id for t in teams],
            status=status,
            limit=limit,
            offset=offset,
        )

    async def list_for_mentor(
        self, user_id: uuid.UUID, *, status: MentoringRequestStatus | None, limit: int, offset: int
    ) -> tuple[list[MentoringRequest], int]:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        return await self._requests.list_for_mentor(
            mentor.id, status=status, limit=limit, offset=offset
        )

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[MentoringRequest], int]:
        return await self._requests.list_by_cohort(
            cohort_id, status=status, mentor_id=mentor_id, limit=limit, offset=offset
        )

    # ------------------------------------------------------------------ 내부
    async def _resolve(
        self, user_id: uuid.UUID, data: RequestInput
    ) -> tuple[Student, uuid.UUID, uuid.UUID, uuid.UUID | None]:
        """(신청자 수강 등록, 기수, 멘토, 팀)."""
        registrations = await self._students.of_user(user_id)
        if data.team_id is not None:
            team = await self._teams.get(data.team_id)
            if team is None:
                raise NotFoundError("팀을 찾을 수 없습니다.", code="team_not_found")
            member = next((s for s in registrations if s.id in team.member_ids), None)
            if member is None:
                raise PermissionDeniedError(
                    "팀원만 팀 신청을 할 수 있습니다.", code="not_team_member"
                )
            requester, cohort_id, mentor_id = member, team.cohort_id, team.mentor_id
        else:
            if data.cohort_id is None or data.mentor_id is None:
                raise BusinessRuleViolation(
                    "1:1 신청은 기수와 멘토를 골라야 합니다.", code="request_target_required"
                )
            found = next((s for s in registrations if s.cohort_id == data.cohort_id), None)
            if found is None:
                raise PermissionDeniedError(
                    "이 기수의 수강생만 신청할 수 있습니다.", code="not_cohort_student"
                )
            requester, cohort_id, mentor_id = found, data.cohort_id, data.mentor_id
        _rule(_active(requester), "수강 중인 수강생만 신청할 수 있습니다.", "student_not_enrolled")
        return requester, cohort_id, mentor_id, data.team_id

    async def _ensure_available(self, request: MentoringRequest, cohort_id: uuid.UUID) -> None:
        slots = request.slots()
        start = min(business_date(s) for s, _ in slots)
        end = max(business_date(e - timedelta(microseconds=1)) for _, e in slots)
        times = await self._availability.times_for(request.mentor_id, cohort_id, start, end)
        _rule(
            times.accepting_requests, "지금은 신청을 받지 않는 멘토입니다.", "mentor_not_accepting"
        )
        for slot_start, slot_end in slots:
            _rule(
                any(i.start <= slot_start and slot_end <= i.end for i in times.intervals),
                "신청할 수 없는 희망 일시가 있습니다.",
                "desired_time_unavailable",
            )

    async def _locked_account(self, request: MentoringRequest) -> BalanceAccount | None:
        found = await self._accounts.find_by_owners(
            student_ids=[] if request.team_id else [request.requester_id],
            team_ids=[request.team_id] if request.team_id else [],
        )
        locked = await self._accounts.lock_many([a.id for a in found])
        return locked[0] if locked else None

    async def _lock_pair(
        self, request: MentoringRequest
    ) -> tuple[BalanceAccount, MentoringRequest]:
        account = await self._locked_account(request)  # 계좌 → 신청 순서로 잠근다
        locked = await self._requests.lock(request.id)
        if account is None or locked is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        return account, locked

    def _cancel(
        self, request: MentoringRequest, account: BalanceAccount, reason: str
    ) -> BalanceTransaction:
        request.cancel(reason, now=self._clock.now())
        return account.release(request.duration, request_id=request.id, reason=RELEASE_REASON)

    async def _persist(
        self, request: MentoringRequest, account: BalanceAccount, entry: BalanceTransaction
    ) -> None:
        await self._requests.save(request)
        await self._accounts.save(account)
        await self._ledger.add_many([entry])

    async def _get(self, request_id: uuid.UUID) -> MentoringRequest:
        request = await self._requests.get(request_id)
        if request is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        return request

    async def _record(
        self, actor_id: uuid.UUID | None, action: str, request: MentoringRequest
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.request.{action}",
            target_type=TARGET,
            target_id=request.id,
            after={
                "status": request.status.value,
                "mentor_id": str(request.mentor_id),
                "team_id": str(request.team_id) if request.team_id else None,
                "duration": request.duration,
                "cancel_reason": request.cancel_reason,
            },
        )

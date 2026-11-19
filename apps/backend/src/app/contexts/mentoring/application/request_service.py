"""멘토링 신청·승인 전 취소·대기 만료·조회 (decisions M1·M5·M9·A41·A42).

신청 (수강생 본인, 대리 신청 없음):
- 1:1은 기수·멘토를 고른다(그 기수 활성 배정 멘토).
- 팀은 팀을 고르면 팀 담당 멘토에게 간다(팀원 누구나).
- 신청자는 그 기수 수강 중이어야 하고, 기수 설정에서 1:1·팀 멘토링이 허용돼 있어야 한다.
- 신청 시간은 진행 단위의 배수(최대 120분).
- 희망 일시는 각각 멘토의 신청 가능 구간(P9 계산) 안이어야 한다.
- 계좌(1:1은 수강생, 팀은 팀)가 있어야 하고, 사용 기간 안의 날짜여야 하며, 대기 신청 수가 기수 설정
  (`max_pending_requests`, 1:1 수강생당·팀 팀당)보다 적어야 한다. 신청 시간만큼 보류(HOLD)한다.
취소 (사유 필수):
- 대기 중: 신청자만 → 보류 해제(RELEASE).
- 승인 후: 신청자·담당 멘토, 시작 `min_lead_hours` 전까지 → 세션 취소 + 전액 환불(REFUND, M26).
- 운영진(기수 범위): 언제든. 대기 신청은 RELEASE, 승인된 신청은 예정 세션만 취소하고 환불 여부를
  고른다(환불 안 함이면 USING 유지) (A42·A44).
변경 (신청자만, 취소할 수 있을 때): 한 트랜잭션에서 기존 신청 취소 + 같은 대상의 새 신청
  (`replaced_request_id`). 새 신청이 검사에 실패하면 취소도 되돌린다 (M3·A42·A44).
대기 만료: 승인 가능한 희망 일시(시작 전)가 남지 않은 대기 신청을 주기 작업이 취소하고 RELEASE.
계좌 → 신청 → 세션 순서로 잠근다. 모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.availability_service import AvailableTimes
from app.contexts.mentoring.application.chat_notices import MentoringNotices
from app.contexts.mentoring.domain.balance import BalanceAccount, BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringCancelActor, MentoringRequestStatus
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    CohortMentoringSettingsRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.request import (
    EXPIRED_REASON,
    MentoringRequest,
    ensure_before_deadline,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.settings import CohortMentoringSettings
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.time import business_date

TARGET = "mentoring_request"
HOLD_REASON = "멘토링 신청"
RELEASE_REASON = "신청 취소"
REFUND_REASON = "승인 후 취소"
CHANGE_REASON = "신청 변경"


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
        self,
        mentor_id: uuid.UUID,
        cohort_id: uuid.UUID,
        start: date,
        end: date,
        *,
        exclude_request_id: uuid.UUID | None = None,
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


@dataclass(frozen=True, slots=True)
class ChangeInput:
    """변경은 같은 대상(멘토, 1:1/팀)에서 내용만 바꾼다 (A44)."""

    topic: str
    detail: str
    desired_times: list[datetime]
    duration: int


@dataclass(frozen=True, slots=True)
class RequestList:
    items: list[MentoringRequest]
    total: int  # 상태 필터를 적용한 건수
    counts: dict[MentoringRequestStatus, int]  # 필터와 무관한 상태별 건수 (A67)


@dataclass(frozen=True, slots=True)
class Prepared:
    """트랜잭션 전에 검사를 마친 새 신청."""

    request: MentoringRequest
    settings: CohortMentoringSettings
    days: list[date]


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
        sessions: MentoringSessionRepository,
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
        notices: MentoringNotices | None = None,
    ) -> None:
        self._notices = notices
        self._requests = requests
        self._sessions = sessions
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
        prepared = await self._prepare(requester, cohort_id, mentor_id, team_id, data)
        async with self._uow:
            account = await self._locked_account(prepared.request)
            await self._place(prepared, account)
            await self._record(user_id, "create", prepared.request)
            if self._notices:
                await self._notices.requested(prepared.request)
        return prepared.request

    # ------------------------------------------------------------------ 취소·변경
    async def cancel(
        self, user_id: uuid.UUID, request_id: uuid.UUID, reason: str
    ) -> MentoringRequest:
        """대기 중은 신청자만, 승인 후는 신청자·담당 멘토가 마감 전까지 (A42·M26)."""
        request = await self._get(request_id)
        requester = await self._requester(request)
        is_requester = requester is not None and requester.user_id == user_id
        if request.status is MentoringRequestStatus.APPROVED:
            mentor = await self._mentors.get_by_user(user_id)
            if not (is_requester or (mentor is not None and mentor.id == request.mentor_id)):
                raise PermissionDeniedError(
                    "신청자나 담당 멘토만 취소할 수 있습니다.", code="not_request_party"
                )
        elif not is_requester:
            raise PermissionDeniedError("신청한 사람만 취소할 수 있습니다.", code="not_requester")
        approved = request.status is MentoringRequestStatus.APPROVED
        lead = await self._lead_hours(requester) if approved else 0
        async with self._uow:
            account, request = await self._lock_pair(request)
            session = await self._sessions.lock_by_request(request.id)
            if request.status is MentoringRequestStatus.APPROVED and session is not None:
                ensure_before_deadline(
                    session.starts_at, min_lead_hours=lead, now=self._clock.now()
                )
            by = MentoringCancelActor.REQUESTER if is_requester else MentoringCancelActor.MENTOR
            entries = self._cancel(request, account, session, reason, refund=True, by=by)
            await self._persist(request, account, entries, session)
            await self._record(user_id, "cancel", request)
            if self._notices:
                await self._notices.canceled(request, session)
        return request

    async def staff_cancel(
        self,
        cohort_id: uuid.UUID,
        request_id: uuid.UUID,
        reason: str,
        *,
        refund: bool,
        actor_id: uuid.UUID,
    ) -> MentoringRequest:
        """운영진 취소: 마감과 무관, 대기 신청은 RELEASE, 승인된 신청은 환불 선택 (A42·A44)."""
        request = await self._get(request_id)
        requester = await self._requester(request)
        if requester is None or requester.cohort_id != cohort_id:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        async with self._uow:
            account, request = await self._lock_pair(request)
            session = await self._sessions.lock_by_request(request.id)
            entries = self._cancel(
                request, account, session, reason, refund=refund, by=MentoringCancelActor.STAFF
            )
            await self._persist(request, account, entries, session)
            await self._record(actor_id, "staff_cancel", request, refund=refund)
            if self._notices:
                await self._notices.canceled(request, session)
        return request

    async def change(
        self, user_id: uuid.UUID, request_id: uuid.UUID, data: ChangeInput
    ) -> MentoringRequest:
        """기존 신청 취소 + 같은 대상의 새 신청 (신청자만, 취소할 수 있을 때)."""
        old = await self._get(request_id)
        requester = await self._requester(old)
        if requester is None or requester.user_id != user_id:
            raise PermissionDeniedError("신청한 사람만 변경할 수 있습니다.", code="not_requester")
        _rule(_active(requester), "수강 중인 수강생만 신청할 수 있습니다.", "student_not_enrolled")
        prepared = await self._prepare(
            requester,
            requester.cohort_id,
            old.mentor_id,
            old.team_id,
            RequestInput(
                topic=data.topic,
                detail=data.detail,
                desired_times=data.desired_times,
                duration=data.duration,
            ),
            replaced=old,
        )
        async with self._uow:
            account, old = await self._lock_pair(old)
            session = await self._sessions.lock_by_request(old.id)
            if old.status is MentoringRequestStatus.APPROVED and session is not None:
                ensure_before_deadline(
                    session.starts_at,
                    min_lead_hours=prepared.settings.min_lead_hours,
                    now=self._clock.now(),
                )
            entries = self._cancel(
                old, account, session, CHANGE_REASON, refund=True, by=MentoringCancelActor.REQUESTER
            )
            await self._persist(old, account, entries, session)
            await self._place(prepared, account)
            await self._record(user_id, "change", prepared.request)
            if self._notices:
                await self._notices.changed(prepared.request)
        return prepared.request

    async def expire_stale(self) -> int:
        """승인 가능한 희망 일시가 없는 대기 신청을 취소한다 (주기 작업, 멱등)."""
        now = self._clock.now()
        expired = 0
        for stale in await self._requests.list_stale(now):
            async with self._uow:
                account, request = await self._lock_pair(stale)
                if not request.is_stale(now):  # 잠그는 사이 처리됐다
                    continue
                entries = self._cancel(
                    request,
                    account,
                    None,
                    EXPIRED_REASON,
                    refund=True,
                    by=MentoringCancelActor.SYSTEM,
                )
                await self._persist(request, account, entries, None)
                await self._record(None, "expire", request)
                if self._notices:
                    await self._notices.canceled(request)
                expired += 1
        return expired

    # ------------------------------------------------------------------ 조회
    async def get_for_user(self, user_id: uuid.UUID, request_id: uuid.UUID) -> MentoringRequest:
        """신청자(1:1)·소속 팀원(팀 신청)·담당 멘토만. 그 밖은 없는 신청으로 본다 (A66)."""
        request = await self._requests.get(request_id)
        if request is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is not None and mentor.id == request.mentor_id:
            return request
        registrations = await self._students.of_user(user_id)
        student_ids = [s.id for s in registrations]
        if request.team_id is None:
            if request.requester_id in student_ids:
                return request
        elif request.team_id in {t.id for t in await self._teams.list_by_students(student_ids)}:
            return request
        raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")

    async def list_mine(
        self,
        user_id: uuid.UUID,
        *,
        statuses: list[MentoringRequestStatus] | None,
        limit: int,
        offset: int,
    ) -> RequestList:
        """본인 1:1 신청과 소속 팀의 신청 (팀원 모두 조회, A42). 상태별 건수는 필터와 무관 (A67)."""
        registrations = await self._students.of_user(user_id)
        student_ids = [s.id for s in registrations]
        team_ids = [t.id for t in await self._teams.list_by_students(student_ids)]
        items, total = await self._requests.list_for_participants(
            student_ids=student_ids,
            team_ids=team_ids,
            statuses=statuses,
            limit=limit,
            offset=offset,
        )
        counts = await self._requests.count_statuses_for_participants(
            student_ids=student_ids, team_ids=team_ids
        )
        return RequestList(items=items, total=total, counts=counts)

    async def list_for_mentor(
        self,
        user_id: uuid.UUID,
        *,
        statuses: list[MentoringRequestStatus] | None,
        limit: int,
        offset: int,
    ) -> RequestList:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        items, total = await self._requests.list_for_mentor(
            mentor.id, statuses=statuses, limit=limit, offset=offset
        )
        counts = await self._requests.count_statuses_for_mentor(mentor.id)
        return RequestList(items=items, total=total, counts=counts)

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        status: MentoringRequestStatus | None,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringRequest], int]:
        return await self._requests.list_by_cohort(
            cohort_id,
            status=status,
            mentor_id=mentor_id,
            limit=limit,
            offset=offset,
            student_id=student_id,
            team_id=team_id,
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

    async def _prepare(
        self,
        requester: Student,
        cohort_id: uuid.UUID,
        mentor_id: uuid.UUID,
        team_id: uuid.UUID | None,
        data: RequestInput,
        *,
        replaced: MentoringRequest | None = None,
    ) -> Prepared:
        """설정·허용 방식·진행 단위·신청 가능 구간 검사 (트랜잭션 밖)."""
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
            replaced_request_id=replaced.id if replaced else None,
        )
        request.ensure_duration_unit(settings.allowed_duration)
        await self._ensure_available(
            request, cohort_id, exclude_request_id=replaced.id if replaced else None
        )
        days = [business_date(start) for start, _ in request.slots()]
        return Prepared(request=request, settings=settings, days=days)

    async def _place(self, prepared: Prepared, account: BalanceAccount | None) -> None:
        """잠긴 계좌로 사용 기간·대기 수를 보고 보류한 뒤 저장한다 (트랜잭션 안)."""
        request, settings = prepared.request, prepared.settings
        if account is None:
            raise BusinessRuleViolation(
                "지급된 멘토링 시간이 없습니다.", code="balance_account_missing"
            )
        _rule(
            all(account.valid_from <= d <= account.valid_until for d in prepared.days),
            "희망 일시가 멘토링 시간 사용 기간 밖입니다.",
            "desired_time_outside_validity",
        )
        pending = await self._requests.count_pending(
            requester_id=None if request.team_id else request.requester_id,
            team_id=request.team_id,
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

    async def _ensure_available(
        self,
        request: MentoringRequest,
        cohort_id: uuid.UUID,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> None:
        slots = request.slots()
        start = min(business_date(s) for s, _ in slots)
        end = max(business_date(e - timedelta(microseconds=1)) for _, e in slots)
        times = await self._availability.times_for(
            request.mentor_id, cohort_id, start, end, exclude_request_id=exclude_request_id
        )
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
        self,
        request: MentoringRequest,
        account: BalanceAccount,
        session: MentoringSession | None,
        reason: str,
        *,
        refund: bool,
        by: MentoringCancelActor,
    ) -> list[BalanceTransaction]:
        """대기 → RELEASE, 승인 → 세션 취소 + (환불이면) REFUND."""
        approved = request.status is MentoringRequestStatus.APPROVED
        request.cancel(reason, now=self._clock.now(), by=by)
        if not approved:
            return [account.release(request.duration, request_id=request.id, reason=RELEASE_REASON)]
        if session is None:
            raise NotFoundError("세션을 찾을 수 없습니다.", code="session_not_found")
        session.cancel()
        if not refund:
            return []
        return [account.refund(request.duration, request_id=request.id, reason=REFUND_REASON)]

    async def _persist(
        self,
        request: MentoringRequest,
        account: BalanceAccount,
        entries: list[BalanceTransaction],
        session: MentoringSession | None,
    ) -> None:
        await self._requests.save(request)
        if session is not None:
            await self._sessions.save(session)
        if entries:
            await self._accounts.save(account)
            await self._ledger.add_many(entries)

    async def _requester(self, request: MentoringRequest) -> Student | None:
        return (await self._students.get_many([request.requester_id])).get(request.requester_id)

    async def _lead_hours(self, requester: Student | None) -> int:
        settings = await self._settings.get_by_cohort(requester.cohort_id) if requester else None
        if settings is None:
            raise NotFoundError(
                "이 기수의 멘토링 설정이 아직 없습니다.", code="mentoring_settings_not_configured"
            )
        return settings.min_lead_hours

    async def _get(self, request_id: uuid.UUID) -> MentoringRequest:
        request = await self._requests.get(request_id)
        if request is None:
            raise NotFoundError("신청을 찾을 수 없습니다.", code="request_not_found")
        return request

    async def _record(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        request: MentoringRequest,
        *,
        refund: bool | None = None,
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
                "replaced_request_id": (
                    str(request.replaced_request_id) if request.replaced_request_id else None
                ),
                "refund": refund,
            },
        )

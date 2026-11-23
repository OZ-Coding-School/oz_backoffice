"""세션 기록 제출·수정, 내부 메모, 기록 미제출 목록 (decisions M22·M27·M28·A53, P13-1).

기록 (담당 멘토만, 예정 시작 이후):
- COMPLETED: 실제 진행 시간(30분 단위, 신청보다 길어도 됨)·주제·요약. 계좌는 실제 진행 시간 기준으로
  맞춘다 — 짧으면 차이를 REFUND, 길면 초과분을 OVERTIME. 잔여가 모자라도 제출은 받고, 잔여만큼만
  차감한 뒤 모자란 분은 세션의 미차감 초과 시간으로 남긴다(A78).
- NO_SHOW: 사유 선택, 신청 시간 전액 REFUND(M28).
- 진행 시간·완료/노쇼는 처음 제출로 고정. 주제·요약만 제출 후 7일까지 수정.
내부 메모: 세션당 하나, 담당 멘토만 쓰고 담당 멘토·운영진(기수 범위)만 본다. 작성·수정은 감사 로그.
운영진은 조회만 한다(대리 제출 없음).
잠금 순서: 계좌 → 신청 → 세션.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.chat_notices import MentoringNotices
from app.contexts.mentoring.domain.balance import BalanceTransaction
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.note import MentoringSessionNote
from app.contexts.mentoring.domain.repositories import (
    BalanceAccountRepository,
    BalanceTransactionRepository,
    MentoringRequestRepository,
    MentoringSessionNoteRepository,
    MentoringSessionRepository,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError, PermissionDeniedError

REFUND_SHORT_REASON = "실제 진행 시간이 신청보다 짧음"
REFUND_NO_SHOW_REASON = "노쇼 환불"
OVERTIME_REASON = "실제 진행 시간이 신청보다 김"


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


@dataclass(frozen=True, slots=True)
class RecordInput:
    status: MentoringSessionStatus  # COMPLETED 또는 NO_SHOW
    summary: str | None  # 완료면 요약(필수), 노쇼면 사유(선택)
    duration: int | None = None  # 완료만
    topic: str | None = None  # 완료만, 없으면 세션 주제


def _not_found() -> NotFoundError:
    return NotFoundError("세션을 찾을 수 없습니다.", code="session_not_found")


class SessionRecordService:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        requests: MentoringRequestRepository,
        notes: MentoringSessionNoteRepository,
        accounts: BalanceAccountRepository,
        ledger: BalanceTransactionRepository,
        students: StudentLookup,
        mentors: MentorLookup,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        notices: MentoringNotices | None = None,
    ) -> None:
        self._notices = notices
        self._sessions = sessions
        self._requests = requests
        self._notes = notes
        self._accounts = accounts
        self._ledger = ledger
        self._students = students
        self._mentors = mentors
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 기록
    async def submit(
        self, user_id: uuid.UUID, session_id: uuid.UUID, data: RecordInput
    ) -> MentoringSession:
        session = await self._own_session(user_id, session_id)
        request = await self._requests.get(session.request_id)
        if request is None:
            raise _not_found()
        found = await self._accounts.find_by_owners(
            student_ids=[] if request.team_id else [request.requester_id],
            team_ids=[request.team_id] if request.team_id else [],
        )
        now = self._clock.now()
        async with self._uow:
            accounts = await self._accounts.lock_many([a.id for a in found])
            await self._requests.lock(request.id)
            locked = await self._sessions.lock(session.id)
            if locked is None or not accounts:
                raise _not_found()
            account = accounts[0]
            entries: list[BalanceTransaction] = []
            if data.status is MentoringSessionStatus.NO_SHOW:
                locked.submit_no_show(reason=data.summary, now=now)
                entries.append(
                    account.refund(
                        request.duration, request_id=request.id, reason=REFUND_NO_SHOW_REASON
                    )
                )
            else:
                locked.submit_completed(
                    duration=data.duration or 0,
                    topic=data.topic if data.topic is not None else locked.topic,
                    summary=data.summary or "",
                    now=now,
                )
                diff = (locked.record_duration_minutes or 0) - request.duration
                if diff < 0:
                    entries.append(
                        account.refund(-diff, request_id=request.id, reason=REFUND_SHORT_REASON)
                    )
                elif diff > 0:
                    charged = min(diff, account.remaining_minutes)
                    if charged > 0:
                        entries.append(
                            account.overtime(charged, request_id=request.id, reason=OVERTIME_REASON)
                        )
                    if diff > charged:
                        locked.note_uncharged_overtime(diff - charged)
            await self._sessions.save(locked)
            if entries:
                await self._accounts.save(account)
                await self._ledger.add_many(entries)
            await self._record(user_id, "record", locked, extra={"requested": request.duration})
            if self._notices:
                await self._notices.recorded(request, locked)
        return locked

    async def edit(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        *,
        topic: str | None,
        summary: str | None,
    ) -> MentoringSession:
        await self._own_session(user_id, session_id)
        async with self._uow:
            locked = await self._sessions.lock(session_id)
            if locked is None:
                raise _not_found()
            locked.edit_record(topic=topic, summary=summary, now=self._clock.now())
            await self._sessions.save(locked)
            await self._record(user_id, "record_edit", locked)
        return locked

    async def unrecorded(
        self, cohort_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[MentoringSession], int]:
        return await self._sessions.list_unrecorded(
            cohort_id, before=self._clock.now(), limit=limit, offset=offset
        )

    # ------------------------------------------------------------------ 내부 메모
    async def my_note(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> MentoringSessionNote | None:
        await self._own_session(user_id, session_id)
        return await self._notes.get_by_session(session_id)

    async def write_note(
        self, user_id: uuid.UUID, session_id: uuid.UUID, body: str
    ) -> MentoringSessionNote:
        session = await self._own_session(user_id, session_id)
        async with self._uow:
            note = await self._notes.get_by_session(session.id)
            before = note.body if note else None
            if note is None:
                note = MentoringSessionNote(session_id=session.id, body=body)
                await self._notes.add(note)
            else:
                note.rewrite(body)
                await self._notes.save(note)
            await self._audit.record(
                actor_user_id=user_id,
                action="mentoring.session.note_write",
                target_type="mentoring_session",
                target_id=session.id,
                before={"length": len(before)} if before is not None else None,
                after={"length": len(note.body)},
            )
        return note

    async def cohort_note(
        self, cohort_id: uuid.UUID, session_id: uuid.UUID
    ) -> MentoringSessionNote | None:
        """운영진 조회 (기수 범위). 다른 기수 세션이면 404."""
        session = await self._sessions.get(session_id)
        if session is None:
            raise _not_found()
        request = await self._requests.get(session.request_id)
        requester = (
            (await self._students.get_many([request.requester_id])).get(request.requester_id)
            if request
            else None
        )
        if requester is None or requester.cohort_id != cohort_id:
            raise _not_found()
        return await self._notes.get_by_session(session_id)

    # ------------------------------------------------------------------ 내부
    async def _own_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> MentoringSession:
        session = await self._sessions.get(session_id)
        if session is None:
            raise _not_found()
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None or mentor.id != session.mentor_id:
            raise PermissionDeniedError(
                "담당 멘토만 기록·메모를 남길 수 있습니다.", code="not_session_mentor"
            )
        return session

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        session: MentoringSession,
        *,
        extra: dict[str, object] | None = None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.session.{action}",
            target_type="mentoring_session",
            target_id=session.id,
            after={
                "status": session.status.value,
                "record_duration_minutes": session.record_duration_minutes,
                "topic": session.topic,
                **(extra or {}),
            },
        )

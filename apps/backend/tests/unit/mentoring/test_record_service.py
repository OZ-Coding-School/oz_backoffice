"""세션 기록·내부 메모 서비스 (인메모리 + 고정 시계, A53·M28)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.record_service import RecordInput, SessionRecordService
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringSessionStatus,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemoryNoteRepository,
    InMemoryRequestRepository,
    InMemorySessionRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

START = datetime(2026, 11, 20, 5, tzinfo=UTC)


class Students:
    def __init__(self, *students: Student) -> None:
        self.items = {s.id: s for s in students}

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.student = Student(
            cohort_id=self.cohort_id,
            name="가수강",
            hrd_net_status=StudentStatus.TRAINING,
            enrolled_at=date(2026, 11, 1),
        )
        self.mentor = Mentor(user_id=new_id())
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.notes = InMemoryNoteRepository()
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.audit_logs = InMemoryAuditLogRepository()
        self.clock = FixedClock(START + timedelta(hours=1))
        self.service = SessionRecordService(
            sessions=self.sessions,
            requests=self.requests,
            notes=self.notes,
            accounts=self.accounts,
            ledger=self.ledger,
            students=Students(self.student),
            mentors=MentorQueries(InMemoryMentorRepository(self.mentor)),
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def session(self, *, minutes: int = 60, balance: int = 180) -> MentoringSession:
        account = BalanceAccount(
            student_id=self.student.id, valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
        )
        account.grant(balance, "지급", today=date(2026, 11, 1))
        request = MentoringRequest(
            requester_id=self.student.id,
            mentor_id=self.mentor.id,
            topic="신청 주제",
            detail="내용",
            desired_times=[START],
            duration=minutes,
        )
        account.hold(minutes, request_id=request.id, reason="신청")
        request.approve(START, now=START - timedelta(days=1))
        account.use(minutes, request_id=request.id, reason="승인")
        await self.accounts.add(account)
        await self.requests.add(request)
        session = MentoringSession(
            mentor_id=self.mentor.id,
            request_id=request.id,
            starts_at=START,
            ends_at=START + timedelta(minutes=minutes),
            title="제목",
            topic="신청 주제",
        )
        await self.sessions.add(session)
        return session

    def account(self) -> BalanceAccount:
        return next(iter(self.accounts.items.values()))

    async def submit(self, session: MentoringSession, **data: Any) -> MentoringSession:
        values: dict[str, Any] = {"status": MentoringSessionStatus.COMPLETED, "summary": "요약"}
        values.update(data)
        user = values.pop("user", self.mentor.user_id)
        return await self.service.submit(user, session.id, RecordInput(**values))


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_shorter_session_refunds_difference(h: Harness) -> None:
    session = await h.session(minutes=60)
    done = await h.submit(session, duration=30)
    assert (done.status, done.record_duration_minutes, done.topic) == (
        MentoringSessionStatus.COMPLETED,
        30,
        "신청 주제",  # 주제를 비우면 세션 주제
    )
    assert (h.account().used_minutes, h.account().remaining_minutes) == (30, 150)
    assert h.ledger.entries[-1].type is MentoringBalanceTransactionType.REFUND
    assert [log.action for log in h.audit_logs.logs] == ["mentoring.session.record"]


async def test_longer_session_charges_overtime(h: Harness) -> None:
    session = await h.session(minutes=60, balance=120)
    with pytest.raises(BusinessRuleViolation) as short:  # 잔여 60분, 초과 90분
        await h.submit(session, duration=150)
    assert short.value.code == "insufficient_balance"
    assert h.sessions.items[session.id].status is MentoringSessionStatus.SCHEDULED
    done = await h.submit(session, duration=120, topic="실제 주제")
    assert (done.record_duration_minutes, done.topic) == (120, "실제 주제")
    assert (h.account().used_minutes, h.account().remaining_minutes) == (120, 0)
    assert h.ledger.entries[-1].type is MentoringBalanceTransactionType.OVERTIME


async def test_exact_duration_no_ledger_and_no_show_refund(h: Harness) -> None:
    exact = await h.session(minutes=60)
    before = len(h.ledger.entries)
    await h.submit(exact, duration=60)
    assert len(h.ledger.entries) == before

    h2 = Harness()
    no_show_session = await h2.session(minutes=60)
    done = await h2.submit(no_show_session, status=MentoringSessionStatus.NO_SHOW, summary=None)
    assert done.status is MentoringSessionStatus.NO_SHOW
    assert (h2.account().used_minutes, h2.account().remaining_minutes) == (0, 180)  # 전액 환불


async def test_permissions_timing_and_edit(h: Harness) -> None:
    session = await h.session()
    with pytest.raises(PermissionDeniedError):
        await h.submit(session, duration=60, user=new_id())
    with pytest.raises(NotFoundError):
        await h.service.submit(
            h.mentor.user_id, new_id(), RecordInput(MentoringSessionStatus.NO_SHOW, None)
        )
    h.clock.set(START - timedelta(minutes=1))
    with pytest.raises(BusinessRuleViolation) as early:
        await h.submit(session, duration=60)
    assert early.value.code == "session_not_started"

    h.clock.set(START + timedelta(hours=1))
    await h.submit(session, duration=60)
    edited = await h.service.edit(h.mentor.user_id, session.id, topic=None, summary="고친 요약")
    assert edited.body == "고친 요약"
    h.clock.set(START + timedelta(days=8, hours=1))
    with pytest.raises(BusinessRuleViolation) as late:
        await h.service.edit(h.mentor.user_id, session.id, topic="t", summary=None)
    assert late.value.code == "record_edit_expired"


async def test_notes_and_unrecorded(h: Harness) -> None:
    session = await h.session()
    assert await h.service.my_note(h.mentor.user_id, session.id) is None
    note = await h.service.write_note(h.mentor.user_id, session.id, "다음엔 테스트")
    again = await h.service.write_note(h.mentor.user_id, session.id, "고친 메모")
    assert (again.id, again.body) == (note.id, "고친 메모")
    with pytest.raises(PermissionDeniedError):
        await h.service.write_note(new_id(), session.id, "남의 메모")
    found = await h.service.cohort_note(h.cohort_id, session.id)
    assert found is not None
    assert found.body == "고친 메모"
    with pytest.raises(NotFoundError):
        await h.service.cohort_note(new_id(), session.id)
    assert [log.action for log in h.audit_logs.logs].count("mentoring.session.note_write") == 2

    h.sessions.cohort_of_student = {h.student.id: h.cohort_id}
    items, total = await h.service.unrecorded(h.cohort_id, limit=10, offset=0)
    assert (total, [s.id for s in items]) == (1, [session.id])
    await h.submit(session, duration=60)
    assert (await h.service.unrecorded(h.cohort_id, limit=10, offset=0))[1] == 0

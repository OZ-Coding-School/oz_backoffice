"""정산 집계·마감 서비스 (인메모리 + 고정 시계, M16·M29·M30·A55)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.settlement_service import SettlementService
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    MentoringSettlementPolicy,
    MentoringSettlementStatus,
    PayUnit,
    SettlementItemType,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryCohortMentorRepository,
    InMemoryRequestRepository,
    InMemorySessionRepository,
    InMemorySettlementRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOV = date(2026, 11, 1)


class Harness:
    def __init__(
        self, policy: MentoringSettlementPolicy = MentoringSettlementPolicy.ACTUAL_DURATION
    ) -> None:
        self.cohort_id = new_id()
        self.mentor = Mentor(user_id=new_id())
        self.mentor_id = self.mentor.id
        self.student_id = new_id()
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.sessions.cohort_of_student = {self.student_id: self.cohort_id}
        self.settlements = InMemorySettlementRepository()
        self.assignment = CohortMentor(
            cohort_id=self.cohort_id,
            mentor_id=self.mentor_id,
            start_date=date(2026, 11, 1),
            cost_settlement_policy=policy,
            pay_unit=PayUnit.HOURLY,
            pay_rate=30000,
            no_show_pay_amount=10000,
        )
        self.audit_logs = InMemoryAuditLogRepository()
        self.clock = FixedClock(datetime(2026, 12, 2, tzinfo=UTC))
        self.service = SettlementService(
            settlements=self.settlements,
            sessions=self.sessions,
            requests=self.requests,
            assignments=InMemoryCohortMentorRepository(self.assignment),
            mentors=MentorQueries(InMemoryMentorRepository(self.mentor)),
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def session(
        self,
        day: int,
        *,
        month: int = 11,
        requested: int = 60,
        recorded: Any = 60,
        no_show: bool = False,
    ) -> MentoringSession:
        start = datetime(2026, month, day, 14, tzinfo=KST)
        request = MentoringRequest(
            requester_id=self.student_id,
            mentor_id=self.mentor_id,
            topic="주제",
            detail="내용",
            desired_times=[start],
            duration=requested,
        )
        await self.requests.add(request)
        session = MentoringSession(
            mentor_id=self.mentor_id,
            request_id=request.id,
            starts_at=start,
            ends_at=start + timedelta(minutes=requested),
            title="제목",
            topic="주제",
        )
        if no_show:
            session.submit_no_show(reason=None, now=start)
        elif recorded is not None:
            session.submit_completed(duration=recorded, topic="주제", summary="요약", now=start)
        await self.sessions.add(session)
        return session


async def test_aggregate_actual_duration_and_no_show() -> None:
    h = Harness()
    await h.session(3, recorded=90)  # 30000 × 90 / 60 = 45000
    await h.session(10, no_show=True)  # 노쇼 고정 10000
    await h.session(5, month=12)  # 다음 달 → 제외
    await h.session(12, recorded=None)  # 기록 전 → 제외
    result = await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())
    (settlement,) = result.settlements
    assert (settlement.session_count, settlement.total_minutes, settlement.total_amount) == (
        2,
        90,
        55000,
    )
    kinds = {i.item_type: i for i in settlement.items}
    assert kinds[SettlementItemType.NO_SHOW].billable_minutes == 0
    assert (
        kinds[SettlementItemType.SESSION].settlement_policy
        is MentoringSettlementPolicy.ACTUAL_DURATION
    )

    again = await h.service.aggregate(
        h.cohort_id, NOV, actor_id=new_id()
    )  # 다시 집계해도 같은 정산서
    assert [s.id for s in again.settlements] == [settlement.id]
    assert len(h.settlements.items) == 1


async def test_student_request_policy() -> None:
    h = Harness(MentoringSettlementPolicy.STUDENT_REQUEST)
    await h.session(3, requested=60, recorded=30)
    (settlement,) = (await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())).settlements
    assert (settlement.total_minutes, settlement.total_amount) == (60, 30000)  # 신청 시간 기준


async def test_close_warns_unrecorded_and_late_sessions_go_next() -> None:
    h = Harness()
    await h.session(3)
    late = await h.session(20, recorded=None)  # 기록 미제출
    (settlement,) = (await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())).settlements
    preview = await h.service.close(h.cohort_id, settlement.id, confirm=False, actor_id=new_id())
    assert (preview.applied, [s.id for s in preview.unrecorded]) == (False, [late.id])
    done = await h.service.close(h.cohort_id, settlement.id, confirm=True, actor_id=new_id())
    assert done.applied
    assert done.settlement.status is MentoringSettlementStatus.CLOSED
    with pytest.raises(BusinessRuleViolation):
        await h.service.close(h.cohort_id, settlement.id, confirm=True, actor_id=new_id())

    # 마감 뒤 늦게 기록 → 11월은 다시 집계하지 않고, 12월 정산에 들어간다
    stored = h.sessions.items[late.id]
    stored.submit_completed(
        duration=60, topic="주제", summary="요약", now=datetime(2026, 12, 3, tzinfo=UTC)
    )
    nov = await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())
    assert ([s.id for s in nov.closed], nov.settlements) == ([settlement.id], [])
    dec = await h.service.aggregate(h.cohort_id, date(2026, 12, 1), actor_id=new_id())
    assert [i.session_id for i in dec.settlements[0].items] == [late.id]


async def test_missing_assignment_is_skipped_and_scope() -> None:
    h = Harness()
    early = await h.session(1)
    h.assignment.start_date = date(2026, 11, 2)
    h.service._assignments = InMemoryCohortMentorRepository(h.assignment)
    result = await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())
    assert [(s.session_id, s.code) for s in result.skipped] == [(early.id, "assignment_not_found")]
    assert result.settlements == []
    with pytest.raises(NotFoundError):
        await h.service.get(new_id(), new_id())


async def test_mentor_sees_only_closed_own() -> None:
    h = Harness()
    await h.session(3)
    (settlement,) = (await h.service.aggregate(h.cohort_id, NOV, actor_id=new_id())).settlements
    assert await h.service.list_for_mentor(h.mentor.user_id) == []  # 집계 중은 안 보인다
    with pytest.raises(NotFoundError):
        await h.service.get_for_mentor(h.mentor.user_id, settlement.id)
    await h.service.close(h.cohort_id, settlement.id, confirm=True, actor_id=new_id())
    assert [s.id for s in await h.service.list_for_mentor(h.mentor.user_id)] == [settlement.id]
    detail = await h.service.get_for_mentor(h.mentor.user_id, settlement.id)
    assert len(detail.items) == 1
    with pytest.raises(NotFoundError):
        await h.service.list_for_mentor(new_id())  # 멘토 프로필 없음

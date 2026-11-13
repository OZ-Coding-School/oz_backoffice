"""멘토링 정산 집계·조회·마감 (decisions M16·M29·M30·A55, P14-1).

- 운영진이 기수·월을 골라 수동으로 집계한다. 멘토마다 DRAFT 정산서를 만들거나 새로 계산한다.
- 대상: 그 기수에서 그 달(KST) 말까지 시작했고 기록(완료·노쇼)이 끝난 세션 중 다른 정산에 들어가지
  않은 것. 그래서 마감 뒤 늦게 기록된 지난달 세션은 다음 정산에 들어간다.
- 명세: 세션 시작일에 유효한 기수 배정의 정산 기준·단가를 스냅샷한다. 배정을 못 찾은 세션은 건너뛰고
  알린다.
- 마감: 기록 미제출 세션이 있으면 목록을 돌려주고, 확인(confirm)하면 마감한다. 마감한 정산은 다시
  집계하지 않는다.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import MentoringSessionStatus, SettlementItemType
from app.contexts.mentoring.domain.repositories import (
    CohortMentorRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringSettlementRepository,
)
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.settlement import (
    MentoringSettlement,
    SettlementItem,
    billable_minutes,
    month_start,
    next_month,
    session_amount,
)
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError
from app.shared.time import KST, business_date

TARGET = "mentoring_settlement"
UNRECORDED_LIMIT = 100


@dataclass(frozen=True, slots=True)
class SkippedSession:
    session_id: uuid.UUID
    code: str


@dataclass(slots=True)
class AggregateResult:
    settlements: list[MentoringSettlement] = field(default_factory=list)
    skipped: list[SkippedSession] = field(default_factory=list)
    closed: list[MentoringSettlement] = field(
        default_factory=list
    )  # 이미 마감돼 다시 집계하지 않음


@dataclass(frozen=True, slots=True)
class CloseResult:
    applied: bool
    settlement: MentoringSettlement
    unrecorded: list[MentoringSession]


def _month_end(month: date) -> datetime:
    """그 달이 끝나는 순간(다음 달 1일 00:00 KST)."""
    return datetime.combine(next_month(month), time(), KST)


def _assignment_for(
    assignments: list[CohortMentor], cohort_id: uuid.UUID, day: date
) -> CohortMentor | None:
    """세션 시작일에 유효한 기수 배정 (여럿이면 가장 최근에 시작한 것)."""
    covering = [
        a
        for a in assignments
        if a.cohort_id == cohort_id
        and a.start_date <= day
        and (a.end_date is None or day <= a.end_date)
    ]
    return max(covering, key=lambda a: a.start_date, default=None)


class SettlementService:
    def __init__(
        self,
        *,
        settlements: MentoringSettlementRepository,
        sessions: MentoringSessionRepository,
        requests: MentoringRequestRepository,
        assignments: CohortMentorRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._settlements = settlements
        self._sessions = sessions
        self._requests = requests
        self._assignments = assignments
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 집계
    async def aggregate(
        self, cohort_id: uuid.UUID, month: date, *, actor_id: uuid.UUID
    ) -> AggregateResult:
        month = month_start(month)
        candidates = await self._sessions.list_settleable(cohort_id, before=_month_end(month))
        by_mentor: dict[uuid.UUID, list[MentoringSession]] = defaultdict(list)
        for session in candidates:
            by_mentor[session.mentor_id].append(session)
        for existing in await self._settlements.list_by_cohort(cohort_id, month=month):
            by_mentor.setdefault(existing.mentor_id, [])  # 대상이 없어져도 DRAFT는 다시 계산
        requests = await self._requests.get_many([s.request_id for s in candidates])
        result = AggregateResult()
        async with self._uow:
            for mentor_id, sessions in by_mentor.items():
                settlement = await self._settlements.get_by_key(mentor_id, cohort_id, month)
                if settlement is not None and settlement.is_closed:
                    result.closed.append(settlement)
                    continue
                is_new = settlement is None
                if settlement is None:
                    settlement = MentoringSettlement(
                        mentor_id=mentor_id, cohort_id=cohort_id, settlement_month=month
                    )
                taken = await self._settlements.settled_session_ids(
                    [s.id for s in sessions], exclude_settlement_id=settlement.id
                )
                assignments = await self._assignments.list_by_mentor(
                    mentor_id, include_inactive=True
                )
                items: list[SettlementItem] = []
                for session in sessions:
                    if session.id in taken:
                        continue
                    item = self._item(session, cohort_id, assignments, requests)
                    if item is None:
                        result.skipped.append(SkippedSession(session.id, "assignment_not_found"))
                    else:
                        items.append(item)
                if not items and is_new:
                    continue  # 새로 만들 정산서에 넣을 세션이 없다
                settlement.replace_items(items)
                await self._settlements.save(settlement)
                result.settlements.append(settlement)
                await self._record(actor_id, "aggregate", settlement)
        return result

    @staticmethod
    def _item(
        session: MentoringSession,
        cohort_id: uuid.UUID,
        assignments: list[CohortMentor],
        requests: dict[uuid.UUID, MentoringRequest],
    ) -> SettlementItem | None:
        assignment = _assignment_for(assignments, cohort_id, business_date(session.starts_at))
        request = requests.get(session.request_id)
        if assignment is None or request is None:
            return None
        if session.status is MentoringSessionStatus.NO_SHOW:
            return SettlementItem(
                session_id=session.id,
                cohort_id=cohort_id,
                item_type=SettlementItemType.NO_SHOW,
                settlement_policy=assignment.cost_settlement_policy,
                billable_minutes=0,
                pay_unit=assignment.pay_unit,
                pay_rate=assignment.no_show_pay_amount,
                amount=assignment.no_show_pay_amount,
                session_starts_at=session.starts_at,
            )
        minutes = billable_minutes(
            assignment.cost_settlement_policy,
            requested=request.duration,
            recorded=session.record_duration_minutes,
        )
        return SettlementItem(
            session_id=session.id,
            cohort_id=cohort_id,
            item_type=SettlementItemType.SESSION,
            settlement_policy=assignment.cost_settlement_policy,
            billable_minutes=minutes,
            pay_unit=assignment.pay_unit,
            pay_rate=assignment.pay_rate,
            amount=session_amount(assignment.pay_unit, assignment.pay_rate, minutes),
            session_starts_at=session.starts_at,
        )

    # ------------------------------------------------------------------ 조회·마감
    async def list_by_cohort(
        self, cohort_id: uuid.UUID, *, month: date | None
    ) -> list[MentoringSettlement]:
        return await self._settlements.list_by_cohort(
            cohort_id, month=month_start(month) if month else None
        )

    async def get(self, cohort_id: uuid.UUID, settlement_id: uuid.UUID) -> MentoringSettlement:
        settlement = await self._settlements.get(settlement_id)
        if settlement is None or settlement.cohort_id != cohort_id:
            raise NotFoundError("정산을 찾을 수 없습니다.", code="settlement_not_found")
        return settlement

    async def close(
        self,
        cohort_id: uuid.UUID,
        settlement_id: uuid.UUID,
        *,
        confirm: bool,
        actor_id: uuid.UUID,
    ) -> CloseResult:
        settlement = await self.get(cohort_id, settlement_id)
        unrecorded, _ = await self._sessions.list_unrecorded(
            cohort_id,
            before=_month_end(settlement.settlement_month),
            limit=UNRECORDED_LIMIT,
            offset=0,
            mentor_id=settlement.mentor_id,
        )
        if unrecorded and not confirm:
            return CloseResult(applied=False, settlement=settlement, unrecorded=unrecorded)
        async with self._uow:
            settlement.close(self._clock.now())
            await self._settlements.save(settlement)
            await self._record(actor_id, "close", settlement, unrecorded=len(unrecorded))
        return CloseResult(applied=True, settlement=settlement, unrecorded=unrecorded)

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        settlement: MentoringSettlement,
        *,
        unrecorded: int | None = None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.settlement.{action}",
            target_type=TARGET,
            target_id=settlement.id,
            after={
                "status": settlement.status.value,
                "month": settlement.settlement_month.isoformat(),
                "session_count": settlement.session_count,
                "total_amount": settlement.total_amount,
                "unrecorded": unrecorded,
            },
        )

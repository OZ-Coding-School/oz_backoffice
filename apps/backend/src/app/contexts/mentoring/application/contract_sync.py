"""계약 변화에 따른 기수 배정 정리 (decisions A110, educator `ContractLifecycleListener`).

- 근거 계약이 ENDED·TERMINATED가 되면 그 계약을 근거로 한 활성 배정을 끈다(CONTRACT_ENDED).
- 근거 계약 기간이 바뀌면 활성 배정 기간을 계약 기간으로 줄이고, 남는 기간이 없으면 끈다.
- 끈 배정은 그 기수의 이 멘토 대기 신청을 자동 취소한다(A42·A45, 수동 비활성화와 같음).
계약 서비스의 트랜잭션 안에서 불리므로 UoW를 열지 않는다. 모든 변경은 감사 로그를 남긴다.
"""

import uuid
from datetime import date

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.application.assignment_service import record_change, snapshot
from app.contexts.mentoring.application.request_cleanup import (
    ASSIGNMENT_DEACTIVATED,
    RequestCleanup,
)
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import CohortMentorDeactivationReason
from app.contexts.mentoring.domain.repositories import CohortMentorRepository
from app.core.clock import Clock


class AssignmentContractSync:
    def __init__(
        self,
        *,
        assignments: CohortMentorRepository,
        cleanup: RequestCleanup,
        audit: AuditRecorder,
        clock: Clock,
    ) -> None:
        self._assignments = assignments
        self._cleanup = cleanup
        self._audit = audit
        self._clock = clock

    async def has_active_assignments(self, contract_id: uuid.UUID) -> bool:
        return bool(await self._assignments.list_active_by_contract(contract_id))

    async def contract_closed(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID | None) -> None:
        for assignment in await self._assignments.list_active_by_contract(contract_id):
            await self._close(assignment, actor_id, snapshot(assignment))

    async def contract_period_changed(
        self,
        contract_id: uuid.UUID,
        *,
        start_date: date | None,
        end_date: date | None,
        actor_id: uuid.UUID | None,
    ) -> None:
        for assignment in await self._assignments.list_active_by_contract(contract_id):
            before = snapshot(assignment)
            if not assignment.trimmed_to(start_date, end_date):
                await self._close(assignment, actor_id, before)
            elif snapshot(assignment) != before:
                await self._assignments.save(assignment)
                await record_change(self._audit, actor_id, "trim", assignment, before)

    async def _close(
        self, assignment: CohortMentor, actor_id: uuid.UUID | None, before: dict[str, object]
    ) -> None:
        assignment.deactivate(CohortMentorDeactivationReason.CONTRACT_ENDED, now=self._clock.now())
        await self._assignments.save(assignment)
        await record_change(self._audit, actor_id, "contract_ended", assignment, before)
        await self._cleanup.cancel_pending_where(
            ASSIGNMENT_DEACTIVATED,
            actor_id=actor_id,
            mentor_id=assignment.mentor_id,
            cohort_id=assignment.cohort_id,
        )

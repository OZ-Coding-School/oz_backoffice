"""멘토 비활성화·재활성화와 배정 복구 (decisions A35·A36, 권한 mentor.manage).

- 비활성화: `confirm=False`면 함께 꺼질 활성 배정만 돌려준다(변경 없음, 안내 문구용).
  `confirm=True`면 멘토를 비활성화하고 활성 배정을 모두 MENTOR_DEACTIVATED로 끈다.
- 재활성화: 멘토를 켜고, 멘토 비활성화로 꺼진 배정 중 다시 켤 수 있는 후보를 돌려준다(추가 팝업).
- 일괄 재활성화: 고른 후보 중 **가능한 것만** 켜고 나머지는 사유와 함께 돌려준다.
멘토 행을 잠가 배정 생성·재활성화와 겹치지 않게 한다. 모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.assignment_service import (
    MentorDirectory,
    ensure_mentor_active,
    record_change,
    snapshot,
)
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import CohortMentorDeactivationReason
from app.contexts.mentoring.domain.repositories import CohortMentorRepository
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError
from app.shared.time import business_date

MENTOR_TARGET = "mentor"


@dataclass(frozen=True, slots=True)
class MentorDeactivation:
    mentor: Mentor
    assignments: list[CohortMentor]  # 함께 꺼지는(confirm=False면 꺼질) 활성 배정
    applied: bool


@dataclass(frozen=True, slots=True)
class MentorActivation:
    mentor: Mentor
    restorable: list[CohortMentor]  # 다시 켤 수 있는 배정 후보


@dataclass(frozen=True, slots=True)
class ReactivationFailure:
    assignment_id: uuid.UUID
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class BulkReactivation:
    reactivated: list[CohortMentor] = field(default_factory=list)
    failed: list[ReactivationFailure] = field(default_factory=list)


def _restorable(
    assignment: CohortMentor, today: date, active_keys: set[tuple[object, ...]]
) -> bool:
    return (
        not assignment.is_active
        and assignment.deactivation_reason is CohortMentorDeactivationReason.MENTOR_DEACTIVATED
        and (assignment.end_date is None or assignment.end_date >= today)
        and _key(assignment) not in active_keys
    )


def _key(assignment: CohortMentor) -> tuple[object, ...]:
    return (assignment.mentor_id, assignment.cohort_id)


class MentorActivationService:
    def __init__(
        self,
        *,
        mentors: MentorDirectory,
        assignments: CohortMentorRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._mentors = mentors
        self._assignments = assignments
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def deactivate(
        self, mentor_id: uuid.UUID, *, confirm: bool, actor_id: uuid.UUID
    ) -> MentorDeactivation:
        if not confirm:
            mentor = await self._mentor(await self._mentors.get(mentor_id))
            active = await self._assignments.list_by_mentor(mentor_id, include_inactive=False)
            return MentorDeactivation(mentor=mentor, assignments=active, applied=False)
        now = self._clock.now()
        async with self._uow:
            mentor = await self._mentor(await self._mentors.lock(mentor_id))
            await self._mentors.set_active(mentor, False)
            active = await self._assignments.list_by_mentor(mentor_id, include_inactive=False)
            for assignment in active:
                before = snapshot(assignment)
                assignment.deactivate(CohortMentorDeactivationReason.MENTOR_DEACTIVATED, now=now)
                await self._assignments.save(assignment)
                await record_change(self._audit, actor_id, "deactivate", assignment, before)
            await self._record_mentor(actor_id, "deactivate", mentor, len(active))
        return MentorDeactivation(mentor=mentor, assignments=active, applied=True)

    async def activate(self, mentor_id: uuid.UUID, *, actor_id: uuid.UUID) -> MentorActivation:
        async with self._uow:
            mentor = await self._mentor(await self._mentors.lock(mentor_id))
            await self._mentors.set_active(mentor, True)
            await self._record_mentor(actor_id, "activate", mentor, None)
        return MentorActivation(mentor=mentor, restorable=await self.restorable(mentor_id))

    async def restorable(self, mentor_id: uuid.UUID) -> list[CohortMentor]:
        today = business_date(self._clock.now())
        assignments = await self._assignments.list_by_mentor(mentor_id, include_inactive=True)
        active_keys = {_key(a) for a in assignments if a.is_active}
        candidates = [a for a in assignments if _restorable(a, today, active_keys)]
        # 같은 기수 후보가 여럿이면 가장 최근에 꺼진 것만 보여 준다
        latest: dict[tuple[object, ...], CohortMentor] = {}
        for candidate in sorted(candidates, key=lambda a: a.deactivated_at or datetime.min):
            latest[_key(candidate)] = candidate
        return [a for a in candidates if latest[_key(a)] is a]

    async def reactivate_assignments(
        self, mentor_id: uuid.UUID, assignment_ids: list[uuid.UUID], *, actor_id: uuid.UUID
    ) -> BulkReactivation:
        """고른 후보 중 가능한 것만 켠다. 멘토가 비활성이면 전체 거부(422 mentor_inactive)."""
        result = BulkReactivation()
        today = business_date(self._clock.now())
        async with self._uow:
            ensure_mentor_active(await self._mentors.lock(mentor_id))
            found = {a.id: a for a in await self._assignments.list_by_ids(assignment_ids)}
            active_keys = {
                _key(a)
                for a in await self._assignments.list_by_mentor(mentor_id, include_inactive=False)
            }
            for assignment_id in dict.fromkeys(assignment_ids):
                assignment = found.get(assignment_id)
                if assignment is None or assignment.mentor_id != mentor_id:
                    result.failed.append(
                        ReactivationFailure(
                            assignment_id,
                            "assignment_not_found",
                            "기수 멘토 배정을 찾을 수 없습니다.",
                        )
                    )
                    continue
                failure = self._why_not(assignment, today, active_keys)
                if failure is not None:
                    result.failed.append(ReactivationFailure(assignment_id, *failure))
                    continue
                before = snapshot(assignment)
                assignment.reactivate(today=today)
                await self._assignments.save(assignment)
                await record_change(self._audit, actor_id, "reactivate", assignment, before)
                active_keys.add(_key(assignment))
                result.reactivated.append(assignment)
        return result

    # ------------------------------------------------------------------ 내부
    @staticmethod
    def _why_not(
        assignment: CohortMentor, today: date, active_keys: set[tuple[object, ...]]
    ) -> tuple[str, str] | None:
        if assignment.is_active:
            return "assignment_already_active", "이미 활성화된 배정입니다."
        if assignment.deactivation_reason is not CohortMentorDeactivationReason.MENTOR_DEACTIVATED:
            return "assignment_not_restorable", "멘토 비활성화로 꺼진 배정만 함께 복구합니다."
        if assignment.end_date is not None and assignment.end_date < today:
            return "assignment_period_ended", "종료일이 지난 배정입니다. 종료일을 먼저 바꾸세요."
        if _key(assignment) in active_keys:
            return "assignment_already_exists", "이 기수에 이미 활성 배정된 멘토입니다."
        return None

    @staticmethod
    async def _mentor(mentor: Mentor | None) -> Mentor:
        if mentor is None:
            raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
        return mentor

    async def _record_mentor(
        self, actor_id: uuid.UUID, action: str, mentor: Mentor, assignment_count: int | None
    ) -> None:
        after: dict[str, object] = {"is_active": mentor.is_active}
        if assignment_count is not None:
            after["deactivated_assignments"] = assignment_count
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"educator.mentor.{action}",
            target_type=MENTOR_TARGET,
            target_id=mentor.id,
            before={"is_active": not mentor.is_active},
            after=after,
        )

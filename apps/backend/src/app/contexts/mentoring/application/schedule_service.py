"""멘토 일정 등록: 불가 시간·신청 받기 (decisions A37).

- 멘토는 불가 시간만 등록하고 그 외는 가능으로 본다(수강생은 기수 운영시간 안에서만 고름).
- 멘토 본인(`/me/...`)과 운영진 대리(`/admin/mentors/{id}/...`, mentor.manage)가 같은 서비스를 쓴다.
- 비활성 멘토는 등록·수정할 수 없다(삭제는 가능). 기수 배정이 없어도 등록할 수 있다.
- 일회성은 시작 전까지만, 반복은 언제든 등록·수정·삭제한다.
- 불가 시간이 늘어나는 변경(등록·수정)은 대기 신청·승인 세션과 충돌하는지 먼저 본다. 충돌이 있으면
  `confirm=True`일 때만 저장하고 충돌 건을 정리한다. P9에서는 충돌 검사 포트가 항상 빈 목록을 준다
  — 실제 검사·반려·취소는 P11, 알림은 M24 결정 후.
- 신청 받기를 끄면 새 신청만 막는다(기존 신청·세션 유지). 비활성 멘토는 켤 수 없다.
모든 변경은 감사 로그를 남긴다.
"""

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.repositories import MentorUnavailablePeriodRepository
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, NotFoundError

TARGET = "mentor_unavailable_period"


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...
    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def set_accepting(self, mentor: Mentor, on: bool) -> None: ...


@dataclass(frozen=True, slots=True)
class ScheduleConflict:
    """변경으로 불가 시간에 걸리는 대기 신청(REQUEST)·승인 세션(SESSION)."""

    kind: Literal["REQUEST", "SESSION"]
    target_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime


class ScheduleConflictFinder(Protocol):
    async def find(
        self, mentor_id: uuid.UUID, unavailable: list[MentorUnavailablePeriod]
    ) -> list[ScheduleConflict]:
        """변경을 반영한 불가 시간 전체에 걸리는 신청·세션."""
        ...


class NoScheduleConflicts:
    """신청·세션(P11)이 생기기 전의 충돌 검사: 항상 충돌 없음."""

    async def find(
        self, mentor_id: uuid.UUID, unavailable: list[MentorUnavailablePeriod]
    ) -> list[ScheduleConflict]:
        return []


@dataclass(frozen=True, slots=True)
class ScheduleChange:
    applied: bool  # False면 충돌 미리보기만 (confirm 필요)
    period: MentorUnavailablePeriod
    conflicts: list[ScheduleConflict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MentorSchedule:
    mentor: Mentor
    unavailable: list[MentorUnavailablePeriod]


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset):
        return sorted(value)
    return value


def _snapshot(period: MentorUnavailablePeriod) -> dict[str, Any]:
    skip = {"id", "created_at", "updated_at"}
    return {
        f.name: _jsonable(getattr(period, f.name))
        for f in dataclasses.fields(period)
        if f.init and f.name not in skip
    }


class MentorScheduleService:
    def __init__(
        self,
        *,
        unavailable_periods: MentorUnavailablePeriodRepository,
        mentors: MentorLookup,
        conflicts: ScheduleConflictFinder,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._periods = unavailable_periods
        self._mentors = mentors
        self._conflicts = conflicts
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 조회
    async def mentor_of_user(self, user_id: uuid.UUID) -> uuid.UUID:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        return mentor.id

    async def view(self, mentor_id: uuid.UUID, *, include_past: bool) -> MentorSchedule:
        mentor = _found(await self._mentors.get(mentor_id))
        periods = await self._periods.list_by_mentor(mentor_id)
        if not include_past:
            now = self._clock.now()
            periods = [p for p in periods if not p.is_finished(now)]
        return MentorSchedule(mentor=mentor, unavailable=periods)

    # ------------------------------------------------------------------ 신청 받기
    async def set_accepting(self, mentor_id: uuid.UUID, on: bool, *, actor_id: uuid.UUID) -> Mentor:
        async with self._uow:
            mentor = _found(await self._mentors.lock(mentor_id))
            before = mentor.accepting_requests
            await self._mentors.set_accepting(mentor, on)
            if before != on:
                await self._audit.record(
                    actor_user_id=actor_id,
                    action="educator.mentor.accepting_requests",
                    target_type="mentor",
                    target_id=mentor_id,
                    before={"accepting_requests": before},
                    after={"accepting_requests": on},
                )
        return mentor

    # ------------------------------------------------------------------ 불가 시간
    async def create(
        self, period: MentorUnavailablePeriod, *, confirm: bool, actor_id: uuid.UUID
    ) -> ScheduleChange:
        period.ensure_changeable(self._clock.now())
        async with self._uow:
            _active(await self._mentors.lock(period.mentor_id))
            current = await self._periods.list_by_mentor(period.mentor_id)
            conflicts = await self._conflicts.find(period.mentor_id, [*current, period])
            if conflicts and not confirm:
                return ScheduleChange(applied=False, period=period, conflicts=conflicts)
            await self._periods.add(period)
            await self._record(actor_id, "create", period, None)
        return ScheduleChange(applied=True, period=period, conflicts=conflicts)

    async def update(
        self,
        mentor_id: uuid.UUID,
        period_id: uuid.UUID,
        replacement: MentorUnavailablePeriod,
        *,
        confirm: bool,
        actor_id: uuid.UUID,
    ) -> ScheduleChange:
        """전체 교체. 일회성은 시작 전만, 반복은 언제든."""
        now = self._clock.now()
        async with self._uow:
            _active(await self._mentors.lock(mentor_id))
            current = await self._periods.list_by_mentor(mentor_id)
            before = _owned(current, period_id)
            before.ensure_changeable(now)
            updated = dataclasses.replace(replacement, id=period_id, mentor_id=mentor_id)
            updated.ensure_changeable(now)
            proposed = [updated if p.id == period_id else p for p in current]
            conflicts = await self._conflicts.find(mentor_id, proposed)
            if conflicts and not confirm:
                return ScheduleChange(applied=False, period=updated, conflicts=conflicts)
            await self._periods.save(updated)
            await self._record(actor_id, "update", updated, before)
        return ScheduleChange(applied=True, period=updated, conflicts=conflicts)

    async def delete(
        self, mentor_id: uuid.UUID, period_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        """가능 시간이 늘어나기만 하므로 충돌 검사는 없다."""
        async with self._uow:
            before = _owned(await self._periods.list_by_mentor(mentor_id), period_id)
            before.ensure_changeable(self._clock.now())
            await self._periods.delete(period_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.unavailable_period.delete",
                target_type=TARGET,
                target_id=period_id,
                before=_snapshot(before),
            )

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        period: MentorUnavailablePeriod,
        before: MentorUnavailablePeriod | None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.unavailable_period.{action}",
            target_type=TARGET,
            target_id=period.id,
            before=_snapshot(before) if before is not None else None,
            after=_snapshot(period),
        )


def _found(mentor: Mentor | None) -> Mentor:
    if mentor is None:
        raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
    return mentor


def _active(mentor: Mentor | None) -> Mentor:
    found = _found(mentor)
    if not found.is_active:
        raise BusinessRuleViolation(
            "비활성화된 멘토는 일정을 등록·수정할 수 없습니다.", code="mentor_inactive"
        )
    return found


def _owned(current: list[MentorUnavailablePeriod], period_id: uuid.UUID) -> MentorUnavailablePeriod:
    for period in current:
        if period.id == period_id:
            return period
    raise NotFoundError("불가 시간을 찾을 수 없습니다.", code="unavailable_period_not_found")

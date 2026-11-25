"""멘토 불가 시간·신청 받기 서비스 (인메모리 리포지토리 + 고정 시계, A37)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.schedule_service import (
    MentorScheduleService,
    NoScheduleConflicts,
    ScheduleConflict,
)
from app.contexts.mentoring.domain.enums import MentoringRequestStatus, UnavailableRepeat
from app.contexts.mentoring.domain.schedule import MentorUnavailablePeriod
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import CleanupStores, InMemoryUnavailablePeriodRepository
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)  # 2026-11-11 12:00 KST
ACTOR = new_id()


class FixedConflicts:
    """P11 충돌 검사를 흉내 낸다: 지정한 충돌을 돌려주고 받은 불가 시간을 기록한다."""

    def __init__(self) -> None:
        self.found: list[ScheduleConflict] = []
        self.seen: list[list[MentorUnavailablePeriod]] = []
        self.resolved: list[list[ScheduleConflict]] = []

    async def find(
        self, mentor_id: uuid.UUID, unavailable: list[MentorUnavailablePeriod]
    ) -> list[ScheduleConflict]:
        self.seen.append(unavailable)
        return list(self.found)

    async def resolve(self, conflicts: list[ScheduleConflict], *, actor_id: uuid.UUID) -> None:
        self.resolved.append(conflicts)


class Harness:
    def __init__(self) -> None:
        self.mentor = Mentor(user_id=new_id())
        self.mentors = InMemoryMentorRepository(self.mentor)
        self.periods = InMemoryUnavailablePeriodRepository()
        self.conflicts = FixedConflicts()
        self.audit_logs = InMemoryAuditLogRepository()
        self.clock = FixedClock(NOW)
        self.stores = CleanupStores(AuditRecorder(self.audit_logs, self.clock), self.clock)
        self.service = MentorScheduleService(
            unavailable_periods=self.periods,
            mentors=MentorQueries(self.mentors),
            conflicts=self.conflicts,
            cleanup=self.stores.cleanup,
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    def once(self, days: int = 3, hours: int = 3) -> MentorUnavailablePeriod:
        start = datetime(2026, 11, 11, 19, tzinfo=KST) + timedelta(days=days)
        return MentorUnavailablePeriod(
            mentor_id=self.mentor.id, starts_at=start, ends_at=start + timedelta(hours=hours)
        )

    def work(self, **overrides: Any) -> MentorUnavailablePeriod:
        values: dict[str, Any] = {
            "mentor_id": self.mentor.id,
            "repeat": UnavailableRepeat.WEEKLY,
            "weekdays": frozenset({1, 2, 3, 4, 5}),
            "starts_at": datetime(2026, 11, 2, 9, tzinfo=KST),  # 이미 시작된 반복
            "ends_at": datetime(2026, 11, 2, 18, tzinfo=KST),
            "category": "근무",
        }
        values.update(overrides)
        return MentorUnavailablePeriod(**values)


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_create_once_and_recurring(h: Harness) -> None:
    once = await h.service.create(h.once(), confirm=False, actor_id=ACTOR)
    assert once.applied
    # 반복은 기준 회차가 지났어도 등록된다, 겹쳐도 된다
    work = await h.service.create(h.work(), confirm=False, actor_id=ACTOR)
    assert work.applied
    await h.service.create(h.once(hours=1), confirm=False, actor_id=ACTOR)
    assert len(h.periods.items) == 3
    with pytest.raises(BusinessRuleViolation) as past:
        await h.service.create(h.once(days=-1), confirm=False, actor_id=ACTOR)
    assert past.value.code == "unavailable_period_started"
    actions = [log.action for log in h.audit_logs.logs]
    assert actions.count("mentoring.unavailable_period.create") == 3


async def test_inactive_or_missing_mentor(h: Harness) -> None:
    h.mentor.deactivate()
    await h.mentors.save(h.mentor)
    with pytest.raises(BusinessRuleViolation) as inactive:
        await h.service.create(h.work(), confirm=False, actor_id=ACTOR)
    assert inactive.value.code == "mentor_inactive"
    with pytest.raises(NotFoundError):
        await h.service.create(h.work(mentor_id=new_id()), confirm=False, actor_id=ACTOR)


async def test_update_and_delete_rules(h: Harness) -> None:
    once = (await h.service.create(h.once(), confirm=False, actor_id=ACTOR)).period
    work = (await h.service.create(h.work(), confirm=False, actor_id=ACTOR)).period

    moved = await h.service.update(
        h.mentor.id, once.id, h.once(days=5), confirm=False, actor_id=ACTOR
    )
    assert moved.period.id == once.id
    assert moved.period.starts_at == datetime(2026, 11, 16, 10, tzinfo=UTC)
    # 반복은 이미 시작됐어도 언제든 고친다
    changed = await h.service.update(
        h.mentor.id, work.id, h.work(repeat_until=date(2026, 12, 31)), confirm=False, actor_id=ACTOR
    )
    assert changed.period.repeat_until == date(2026, 12, 31)
    # 반복을 일회성으로 바꿀 때는 시작 전이어야 한다
    with pytest.raises(BusinessRuleViolation):
        await h.service.update(h.mentor.id, work.id, h.once(days=-2), confirm=False, actor_id=ACTOR)

    h.clock.set(datetime(2026, 11, 16, 11, tzinfo=UTC))  # 일회성 일정이 시작됨
    with pytest.raises(BusinessRuleViolation):
        await h.service.update(h.mentor.id, once.id, h.once(days=9), confirm=False, actor_id=ACTOR)
    with pytest.raises(BusinessRuleViolation):
        await h.service.delete(h.mentor.id, once.id, actor_id=ACTOR)
    await h.service.delete(h.mentor.id, work.id, actor_id=ACTOR)
    with pytest.raises(NotFoundError) as missing:
        await h.service.delete(h.mentor.id, work.id, actor_id=ACTOR)
    assert missing.value.code == "unavailable_period_not_found"
    with pytest.raises(NotFoundError):  # 다른 멘토의 불가 시간
        await h.service.update(new_id(), once.id, h.once(), confirm=False, actor_id=ACTOR)


async def test_conflicts_need_confirm(h: Harness) -> None:
    start = datetime(2026, 11, 16, 10, tzinfo=KST)
    conflict = ScheduleConflict(
        kind="SESSION", target_id=new_id(), starts_at=start, ends_at=start + timedelta(hours=1)
    )
    h.conflicts.found = [conflict]

    preview = await h.service.create(h.work(), confirm=False, actor_id=ACTOR)
    assert (preview.applied, preview.conflicts) == (False, [conflict])
    assert h.periods.items == {}  # 미리보기는 저장하지 않는다
    assert [p.category for p in h.conflicts.seen[-1]] == ["근무"]  # 변경 후 불가 시간 전체

    assert h.conflicts.resolved == []  # 미리보기는 정리하지 않는다
    applied = await h.service.create(h.work(), confirm=True, actor_id=ACTOR)
    assert applied.applied
    assert h.conflicts.resolved == [[conflict]]
    preview_update = await h.service.update(
        h.mentor.id,
        applied.period.id,
        h.work(ends_at=datetime(2026, 11, 2, 19, tzinfo=KST)),
        confirm=False,
        actor_id=ACTOR,
    )
    assert not preview_update.applied
    stored = await h.periods.get(applied.period.id)
    assert stored is not None
    assert stored.ends_at == datetime(2026, 11, 2, 9, tzinfo=UTC)  # 18:00 KST 그대로
    # 삭제는 가능 시간이 늘어나므로 충돌 검사 없이 지운다
    await h.service.delete(h.mentor.id, applied.period.id, actor_id=ACTOR)
    assert h.periods.items == {}


async def test_accepting_switch_and_view(h: Harness) -> None:
    mentor, canceled = await h.service.set_accepting(h.mentor.id, True, actor_id=ACTOR)
    assert (mentor.accepting_requests, canceled) == (True, 0)
    await h.service.set_accepting(h.mentor.id, True, actor_id=ACTOR)  # 같은 값은 기록 안 함
    assert [log.action for log in h.audit_logs.logs] == ["educator.mentor.accepting_requests"]

    await h.periods.add(h.once(days=-5))  # 지난 일회성
    await h.periods.add(h.work(repeat_until=date(2026, 11, 10)))  # 끝난 반복
    await h.periods.add(h.work())
    view = await h.service.view(h.mentor.id, include_past=False)
    assert view.mentor.accepting_requests
    assert [p.repeat_until for p in view.unavailable] == [None]
    assert len((await h.service.view(h.mentor.id, include_past=True)).unavailable) == 3

    h.mentor.deactivate()
    await h.mentors.save(h.mentor)
    with pytest.raises(BusinessRuleViolation):
        await h.service.set_accepting(h.mentor.id, True, actor_id=ACTOR)


async def test_mentor_lookup(h: Harness) -> None:
    assert await h.service.mentor_of_user(h.mentor.account_id) == h.mentor.id
    with pytest.raises(NotFoundError) as missing:
        await h.service.mentor_of_user(new_id())
    assert missing.value.code == "mentor_profile_not_found"
    assert await NoScheduleConflicts().find(new_id(), []) == []


async def test_accepting_off_cancels_pending(h: Harness) -> None:
    await h.service.set_accepting(h.mentor.id, True, actor_id=ACTOR)
    mine = await h.stores.pending(mentor_id=h.mentor.id)
    other = await h.stores.pending(mentor_id=new_id())
    _, canceled = await h.service.set_accepting(h.mentor.id, False, actor_id=ACTOR)
    assert canceled == 1
    assert (h.stores.status(mine), h.stores.status(other)) == (
        MentoringRequestStatus.CANCELED,
        MentoringRequestStatus.PENDING,
    )
    _, again = await h.service.set_accepting(h.mentor.id, False, actor_id=ACTOR)  # 이미 꺼짐
    assert again == 0

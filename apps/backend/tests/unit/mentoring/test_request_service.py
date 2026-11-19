"""멘토링 신청·승인 전 취소·대기 만료 서비스 (인메모리 + 고정 시계, A42)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.availability_service import AvailableTimes
from app.contexts.mentoring.application.request_service import (
    ChangeInput,
    MentoringRequestService,
    RequestInput,
)
from app.contexts.mentoring.domain.availability import Interval
from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringCancelActor,
    MentoringRequestStatus,
    MentoringSessionStatus,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.settings import CohortMentoringSettings
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError
from app.shared.ids import new_id
from app.shared.time import KST
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryBalanceAccountRepository,
    InMemoryBalanceLedger,
    InMemoryRequestRepository,
    InMemorySessionRepository,
    InMemorySettingsRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 11, 3, tzinfo=UTC)  # 2026-11-11 12:00 KST
DAY = date(2026, 11, 16)
T = datetime(2026, 11, 16, 14, tzinfo=KST)


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, cohort_id: uuid.UUID, **overrides: Any) -> Student:
        values: dict[str, Any] = {
            "cohort_id": cohort_id,
            "name": "수강생",
            "hrd_net_status": StudentStatus.TRAINING,
            "enrolled_at": date(2026, 11, 1),
            "user_id": new_id(),
        }
        values.update(overrides)
        student = Student(**values)
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


class Availability:
    """멘토의 신청 가능 구간을 고정한다 (11/16 10:00~19:00 KST)."""

    def __init__(self) -> None:
        self.accepting = True
        self.intervals = [
            Interval(
                datetime(2026, 11, 16, 10, tzinfo=KST).astimezone(UTC),
                datetime(2026, 11, 16, 19, tzinfo=KST).astimezone(UTC),
            )
        ]

    async def times_for(
        self,
        mentor_id: uuid.UUID,
        cohort_id: uuid.UUID,
        start: date,
        end: date,
        *,
        exclude_request_id: uuid.UUID | None = None,
    ) -> AvailableTimes:
        return AvailableTimes(
            mentor_id=mentor_id,
            cohort_id=cohort_id,
            accepting_requests=self.accepting,
            allowed_duration=30,
            min_lead_hours=24,
            intervals=self.intervals if self.accepting else [],
        )


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.mentor = Mentor(user_id=new_id(), accepting_requests=True)
        self.students = Students()
        self.student = self.students.add(self.cohort_id)
        self.teams = InMemoryTeamRepository()
        self.accounts = InMemoryBalanceAccountRepository()
        self.ledger = InMemoryBalanceLedger()
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.settings = InMemorySettingsRepository(
            CohortMentoringSettings(
                cohort_id=self.cohort_id,
                allow_1_on_1=True,
                allow_team_mentoring=True,
                max_pending_requests=2,
            )
        )
        self.availability = Availability()
        self.clock = FixedClock(NOW)
        self.audit_logs = InMemoryAuditLogRepository()
        self.service = MentoringRequestService(
            requests=self.requests,
            sessions=self.sessions,
            accounts=self.accounts,
            ledger=self.ledger,
            teams=self.teams,
            settings=self.settings,
            students=self.students,
            mentors=MentorQueries(InMemoryMentorRepository(self.mentor)),
            availability=self.availability,
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def fund(
        self, *, student_id: Any = None, team_id: Any = None, minutes: int = 180
    ) -> BalanceAccount:
        account = BalanceAccount(
            student_id=student_id if team_id is None else None,
            team_id=team_id,
            valid_from=date(2026, 11, 1),
            valid_until=date(2027, 4, 30),
        )
        account.grant(minutes, "지급", today=date(2026, 11, 11))
        await self.accounts.add(account)
        return account

    def data(self, **overrides: Any) -> RequestInput:
        values: dict[str, Any] = {
            "topic": "포트폴리오 리뷰",
            "detail": "구조를 봐 주세요",
            "desired_times": [T, T + timedelta(hours=2)],
            "duration": 60,
            "cohort_id": self.cohort_id,
            "mentor_id": self.mentor.id,
        }
        values.update(overrides)
        return RequestInput(**values)

    async def approved(self, at: datetime = T, **overrides: Any) -> tuple[Any, MentoringSession]:
        """신청 → 승인 (승인 서비스와 같은 저장 결과를 직접 만든다)."""
        request = await self.create(**overrides)
        stored = self.requests.items[request.id]
        start, end = stored.approve(at, now=self.clock.now())
        session = MentoringSession(
            mentor_id=stored.mentor_id,
            request_id=stored.id,
            starts_at=start,
            ends_at=end,
            title="제목",
            topic=stored.topic,
        )
        await self.sessions.add(session)
        account = next(
            a
            for a in self.accounts.items.values()
            if (
                a.team_id == stored.team_id
                if stored.team_id
                else a.student_id == stored.requester_id
            )
        )
        await self.ledger.add_many(
            [account.use(stored.duration, request_id=stored.id, reason="승인")]
        )
        return stored, session

    async def create(self, **overrides: Any) -> Any:
        user = overrides.pop("user", self.student.user_id)
        return await self.service.create(user, self.data(**overrides))


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_create_holds_time(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id)
    request = await h.create()
    assert request.status is MentoringRequestStatus.PENDING
    stored = h.accounts.items[account.id]
    assert (stored.remaining_minutes, stored.held_minutes) == (120, 60)
    (entry,) = [e for e in h.ledger.entries if e.request_id == request.id]
    assert (entry.type, entry.amount) == (MentoringBalanceTransactionType.HOLD, 60)
    assert [log.action for log in h.audit_logs.logs] == ["mentoring.request.create"]


async def test_create_rules(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as no_account:
        await h.create()
    assert no_account.value.code == "balance_account_missing"
    await h.fund(student_id=h.student.id, minutes=60)

    cases: list[tuple[dict[str, Any], str]] = [
        ({"desired_times": [T.replace(hour=18, minute=30)]}, "desired_time_unavailable"),
        ({"desired_times": [T.replace(hour=9)]}, "desired_time_unavailable"),
        ({"duration": 120}, "insufficient_balance"),
        ({"cohort_id": None}, "request_target_required"),
    ]
    for overrides, code in cases:
        with pytest.raises(BusinessRuleViolation) as error:
            await h.create(**overrides)
        assert error.value.code == code, overrides
    with pytest.raises(PermissionDeniedError):  # 다른 기수 수강생
        await h.create(cohort_id=new_id())

    h.availability.accepting = False
    with pytest.raises(BusinessRuleViolation) as closed:
        await h.create()
    assert closed.value.code == "mentor_not_accepting"


async def test_duration_unit_mode_and_enrollment(h: Harness) -> None:
    await h.fund(student_id=h.student.id)
    h.settings.items[h.cohort_id] = CohortMentoringSettings(
        cohort_id=h.cohort_id, allow_team_mentoring=True, allowed_duration=60
    )
    with pytest.raises(BusinessRuleViolation) as mode:  # 1:1 미허용
        await h.create()
    assert mode.value.code == "mentoring_mode_not_allowed"
    h.settings.items[h.cohort_id] = CohortMentoringSettings(
        cohort_id=h.cohort_id, allow_1_on_1=True, allowed_duration=60
    )
    with pytest.raises(BusinessRuleViolation) as unit:
        await h.create(duration=90)
    assert unit.value.code == "invalid_request_duration"

    dropped = h.students.add(h.cohort_id, status=EnrollmentStatus.DROPPED)
    with pytest.raises(BusinessRuleViolation) as ended:
        await h.create(user=dropped.user_id)
    assert ended.value.code == "student_not_enrolled"


async def test_pending_limit_and_validity(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id)
    await h.create(desired_times=[T])
    await h.create(desired_times=[T])  # 같은 시각 대기 신청끼리는 겹쳐도 된다
    with pytest.raises(BusinessRuleViolation) as limit:
        await h.create(desired_times=[T])
    assert limit.value.code == "too_many_pending_requests"

    stored = h.accounts.items[account.id]
    stored.valid_until = date(2026, 11, 15)
    other = h.students.add(h.cohort_id)
    short = await h.fund(student_id=other.id)
    h.accounts.items[short.id].valid_until = date(2026, 11, 15)
    with pytest.raises(BusinessRuleViolation) as outside:
        await h.create(user=other.user_id)
    assert outside.value.code == "desired_time_outside_validity"


async def test_team_request(h: Harness) -> None:
    team = MentoringTeam(
        cohort_id=h.cohort_id, team_number=1, mentor_id=h.mentor.id, member_ids=[h.student.id]
    )
    await h.teams.add(team)
    account = await h.fund(team_id=team.id)
    request = await h.create(team_id=team.id, cohort_id=None, mentor_id=None)
    assert (request.team_id, request.mentor_id) == (team.id, h.mentor.id)
    assert h.accounts.items[account.id].held_minutes == 60

    outsider = h.students.add(h.cohort_id)
    with pytest.raises(PermissionDeniedError) as not_member:
        await h.create(user=outsider.user_id, team_id=team.id)
    assert not_member.value.code == "not_team_member"
    with pytest.raises(NotFoundError):
        await h.create(team_id=new_id())

    mine, total = await h.service.list_mine(h.student.user_id, status=None, limit=10, offset=0)  # type: ignore[arg-type]
    assert (total, [r.id for r in mine]) == (1, [request.id])


async def test_get_for_user(h: Harness) -> None:
    """신청자·소속 팀원·담당 멘토만 단건을 본다. 그 밖은 없는 신청 (A66)."""
    await h.fund(student_id=h.student.id)
    one = await h.create()
    mate = h.students.add(h.cohort_id)
    team = MentoringTeam(
        cohort_id=h.cohort_id,
        team_number=1,
        mentor_id=h.mentor.id,
        member_ids=[h.student.id, mate.id],
    )
    await h.teams.add(team)
    await h.fund(team_id=team.id)
    team_request = await h.create(team_id=team.id, cohort_id=None, mentor_id=None)
    outsider = h.students.add(h.cohort_id)

    assert (await h.service.get_for_user(h.student.user_id, one.id)).id == one.id  # type: ignore[arg-type]
    assert (await h.service.get_for_user(h.mentor.user_id, one.id)).id == one.id
    assert (await h.service.get_for_user(mate.user_id, team_request.id)).id == team_request.id  # type: ignore[arg-type]
    for user, request_id in (
        (mate.user_id, one.id),  # 다른 사람의 1:1
        (outsider.user_id, team_request.id),  # 팀원이 아님
        (new_id(), one.id),
        (h.student.user_id, new_id()),  # 없는 신청
    ):
        with pytest.raises(NotFoundError) as missing:
            await h.service.get_for_user(user, request_id)  # type: ignore[arg-type]
        assert missing.value.code == "request_not_found"


async def test_cancel_and_expire(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id)
    first = await h.create()
    second = await h.create(desired_times=[T + timedelta(hours=3)])

    with pytest.raises(PermissionDeniedError):
        await h.service.cancel(new_id(), first.id, "남의 신청")
    with pytest.raises(BusinessRuleViolation):  # 사유 필수
        await h.service.cancel(h.student.user_id, first.id, " ")  # type: ignore[arg-type]
    canceled = await h.service.cancel(h.student.user_id, first.id, "일정 변경")  # type: ignore[arg-type]
    assert canceled.status is MentoringRequestStatus.CANCELED
    assert canceled.canceled_by is MentoringCancelActor.REQUESTER
    assert h.accounts.items[account.id].held_minutes == 60

    h.clock.set(datetime(2026, 11, 16, 16, 30, tzinfo=KST))  # 둘째 신청(17시)은 아직 승인 가능
    assert await h.service.expire_stale() == 0
    h.clock.set(datetime(2026, 11, 16, 17, tzinfo=KST))  # 시작 시각 → 만료
    assert await h.service.expire_stale() == 1
    assert await h.service.expire_stale() == 0
    expired = h.requests.items[second.id]
    assert (expired.status, expired.cancel_reason, expired.canceled_by) == (
        MentoringRequestStatus.CANCELED,
        "승인 기한 지남",
        MentoringCancelActor.SYSTEM,
    )
    stored = h.accounts.items[account.id]
    assert (stored.held_minutes, stored.remaining_minutes) == (0, 180)
    assert [e.type for e in h.ledger.entries].count(MentoringBalanceTransactionType.RELEASE) == 2


async def test_mentor_list(h: Harness) -> None:
    await h.fund(student_id=h.student.id)
    await h.create()
    items, total = await h.service.list_for_mentor(
        h.mentor.user_id, status=MentoringRequestStatus.PENDING, limit=10, offset=0
    )
    assert total == 1
    with pytest.raises(NotFoundError):
        await h.service.list_for_mentor(new_id(), status=None, limit=10, offset=0)
    assert len(items) == 1


async def test_cancel_after_approval(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id)
    request, session = await h.approved()
    user = h.student.user_id
    assert user is not None
    with pytest.raises(PermissionDeniedError) as stranger:
        await h.service.cancel(new_id(), request.id, "남")
    assert stranger.value.code == "not_request_party"

    h.clock.set(T - timedelta(hours=23))  # 마감(24시간 전) 지남
    with pytest.raises(BusinessRuleViolation) as late:
        await h.service.cancel(user, request.id, "늦은 취소")
    assert late.value.code == "cancel_deadline_passed"

    h.clock.set(T - timedelta(hours=24))
    canceled = await h.service.cancel(h.mentor.user_id, request.id, "멘토 사정")  # 멘토도 가능
    assert canceled.status is MentoringRequestStatus.CANCELED
    assert canceled.canceled_by is MentoringCancelActor.MENTOR
    assert h.sessions.items[session.id].status is MentoringSessionStatus.CANCELED
    stored = h.accounts.items[account.id]
    assert (stored.used_minutes, stored.remaining_minutes) == (0, 180)
    assert h.ledger.entries[-1].type is MentoringBalanceTransactionType.REFUND


async def test_staff_cancel(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id, minutes=240)
    pending = await h.create(desired_times=[T + timedelta(hours=3)])
    request, session = await h.approved()
    h.clock.set(T + timedelta(hours=2))  # 시작이 지났어도 기록 전이면 운영진은 취소
    with pytest.raises(NotFoundError):  # 다른 기수
        await h.service.staff_cancel(new_id(), request.id, "정리", refund=True, actor_id=new_id())
    no_refund = await h.service.staff_cancel(
        h.cohort_id, request.id, "노쇼 정리", refund=False, actor_id=new_id()
    )
    assert no_refund.status is MentoringRequestStatus.CANCELED
    assert no_refund.canceled_by is MentoringCancelActor.STAFF
    assert h.sessions.items[session.id].status is MentoringSessionStatus.CANCELED
    assert h.accounts.items[account.id].used_minutes == 60  # 환불 안 함 → USING 유지

    released = await h.service.staff_cancel(  # 대기 신청은 환불 선택과 무관하게 해제
        h.cohort_id, pending.id, "운영 정리", refund=False, actor_id=new_id()
    )
    assert released.status is MentoringRequestStatus.CANCELED
    stored = h.accounts.items[account.id]
    assert (stored.held_minutes, stored.remaining_minutes) == (0, 180)
    assert [log.action for log in h.audit_logs.logs][-1] == "mentoring.request.staff_cancel"

    other, other_session = await h.approved(
        desired_times=[T + timedelta(hours=4)], at=T + timedelta(hours=4)
    )
    h.sessions.items[other_session.id].status = MentoringSessionStatus.COMPLETED
    with pytest.raises(BusinessRuleViolation) as done:
        await h.service.staff_cancel(
            h.cohort_id, other.id, "완료됨", refund=True, actor_id=new_id()
        )
    assert done.value.code == "session_not_cancelable"


async def test_change(h: Harness) -> None:
    account = await h.fund(student_id=h.student.id)
    request, session = await h.approved()
    user = h.student.user_id
    assert user is not None
    data = ChangeInput(topic="새 주제", detail="새 내용", desired_times=[T], duration=30)
    with pytest.raises(PermissionDeniedError):
        await h.service.change(h.mentor.user_id, request.id, data)  # 멘토는 변경 불가

    changed = await h.service.change(user, request.id, data)  # 기존 세션 시각도 다시 고를 수 있다
    assert (changed.replaced_request_id, changed.mentor_id, changed.status) == (
        request.id,
        h.mentor.id,
        MentoringRequestStatus.PENDING,
    )
    old = h.requests.items[request.id]
    assert (old.status, old.canceled_by) == (
        MentoringRequestStatus.CANCELED,
        MentoringCancelActor.REQUESTER,
    )
    assert h.sessions.items[session.id].status is MentoringSessionStatus.CANCELED
    stored = h.accounts.items[account.id]
    assert (stored.used_minutes, stored.held_minutes, stored.remaining_minutes) == (0, 30, 150)
    assert [e.type for e in h.ledger.entries][-2:] == [
        MentoringBalanceTransactionType.REFUND,
        MentoringBalanceTransactionType.HOLD,
    ]

    # 새 신청이 검사에 실패하면 기존 신청은 그대로 (검사가 트랜잭션 전에 끝난다)
    bad = ChangeInput(topic="x", detail="y", desired_times=[T.replace(hour=9)], duration=30)
    with pytest.raises(BusinessRuleViolation) as unavailable:
        await h.service.change(user, changed.id, bad)
    assert unavailable.value.code == "desired_time_unavailable"
    assert h.requests.items[changed.id].status is MentoringRequestStatus.PENDING
    too_long = ChangeInput(topic="x", detail="y", desired_times=[T], duration=240)
    with pytest.raises(BusinessRuleViolation):
        await h.service.change(user, changed.id, too_long)
    assert h.requests.items[changed.id].status is MentoringRequestStatus.PENDING

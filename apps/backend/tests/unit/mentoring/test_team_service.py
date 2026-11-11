"""멘토링 팀 구성 서비스 (인메모리, A39)."""

import uuid
from datetime import UTC, date, datetime

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.team_service import MentoringTeamService
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    MentoringPeriodType,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.contexts.mentoring.domain.settings import CohortMentoringSettings
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryCohortMentorRepository,
    InMemorySettingsRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

ACTOR = new_id()
PROJECT = MentoringPeriodType.PROJECT_MENTORING
REGULAR = MentoringPeriodType.REGULAR_MENTORING


class Students:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Student] = {}

    def add(self, cohort_id: uuid.UUID, **overrides: object) -> Student:
        values: dict[str, object] = {
            "cohort_id": cohort_id,
            "name": f"수강생{len(self.items) + 1}",
            "hrd_net_status": StudentStatus.TRAINING,
            "enrolled_at": date(2026, 11, 1),
        }
        values.update(overrides)
        student = Student(**values)  # type: ignore[arg-type]
        self.items[student.id] = student
        return student

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in student_ids if i in self.items}

    async def enrolled_in_cohort(self, cohort_id: uuid.UUID) -> list[Student]:
        return sorted(
            (
                s
                for s in self.items.values()
                if s.cohort_id == cohort_id and s.is_enrolled and not s.is_removed_in_source
            ),
            key=lambda s: s.name,
        )

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


def _assignment(
    mentor: Mentor, cohort_id: uuid.UUID, period_type: MentoringPeriodType
) -> CohortMentor:
    return CohortMentor(
        cohort_id=cohort_id,
        mentor_id=mentor.id,
        period_type=period_type,
        start_date=date(2026, 11, 1),
        cost_settlement_policy=MentoringSettlementPolicy.ACTUAL_DURATION,
        pay_unit=PayUnit.HOURLY,
        pay_rate=30000,
    )


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.mentor = Mentor(user_id=new_id())
        self.other_mentor = Mentor(user_id=new_id())
        self.settings = InMemorySettingsRepository(
            CohortMentoringSettings(cohort_id=self.cohort_id, allow_team_mentoring=True)
        )
        self.assignments = InMemoryCohortMentorRepository(
            _assignment(self.mentor, self.cohort_id, PROJECT),
            _assignment(self.other_mentor, self.cohort_id, PROJECT),
        )
        self.teams = InMemoryTeamRepository()
        self.students = Students()
        self.audit_logs = InMemoryAuditLogRepository()
        self.service = MentoringTeamService(
            teams=self.teams,
            settings=self.settings,
            assignments=self.assignments,
            students=self.students,
            mentors=MentorQueries(InMemoryMentorRepository(self.mentor, self.other_mentor)),
            audit=AuditRecorder(self.audit_logs, FixedClock(datetime(2026, 11, 11, tzinfo=UTC))),
            uow=FakeUnitOfWork(),
        )

    async def create(self, *members: uuid.UUID, **overrides: object) -> uuid.UUID:
        values: dict[str, object] = {
            "period_type": PROJECT,
            "mentor_id": self.mentor.id,
            "name": None,
            "student_ids": list(members),
            "actor_id": ACTOR,
        }
        values.update(overrides)
        team = await self.service.create(self.cohort_id, **values)  # type: ignore[arg-type]
        return team.id


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_create_numbers_and_members(h: Harness) -> None:
    a = h.students.add(h.cohort_id).id
    b = h.students.add(h.cohort_id, user_id=new_id()).id
    first = await h.create(a)
    second = await h.create(b, name="베타")
    teams = await h.service.list_by_cohort(h.cohort_id, PROJECT)
    assert [(t.team_number, t.label) for t in teams] == [(1, "1팀"), (2, "베타")]
    assert teams[0].id == first
    assert teams[1].member_ids == [b]
    assert second != first
    with pytest.raises(ConflictError) as dup:
        await h.create(a)
    assert dup.value.code == "student_in_other_team"


async def test_create_rules(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as unassigned:
        await h.create(period_type=REGULAR)
    assert unassigned.value.code == "mentor_not_assigned"
    dropped = h.students.add(h.cohort_id, status=EnrollmentStatus.DROPPED).id
    with pytest.raises(BusinessRuleViolation) as not_enrolled:
        await h.create(dropped)
    assert not_enrolled.value.code == "student_not_enrolled"
    removed = h.students.add(h.cohort_id, is_removed_in_source=True).id
    with pytest.raises(BusinessRuleViolation):
        await h.create(removed)
    elsewhere = h.students.add(new_id()).id
    with pytest.raises(NotFoundError):
        await h.create(elsewhere)

    h.settings.items[h.cohort_id] = CohortMentoringSettings(
        cohort_id=h.cohort_id, allow_1_on_1=True
    )
    with pytest.raises(BusinessRuleViolation) as not_allowed:
        await h.create()
    assert not_allowed.value.code == "team_mentoring_not_allowed"
    del h.settings.items[h.cohort_id]
    with pytest.raises(NotFoundError):
        await h.create()


async def test_update_members_and_delete(h: Harness) -> None:
    a, b = h.students.add(h.cohort_id).id, h.students.add(h.cohort_id).id
    team_id = await h.create(a)
    updated = await h.service.update(
        h.cohort_id, team_id, {"name": "알파", "mentor_id": h.other_mentor.id}, actor_id=ACTOR
    )
    assert (updated.name, updated.mentor_id) == ("알파", h.other_mentor.id)
    with pytest.raises(BusinessRuleViolation):
        await h.service.update(h.cohort_id, team_id, {"mentor_id": new_id()}, actor_id=ACTOR)

    await h.service.add_member(h.cohort_id, team_id, b, actor_id=ACTOR)
    with pytest.raises(ConflictError):
        await h.service.add_member(h.cohort_id, team_id, b, actor_id=ACTOR)
    removed = await h.service.remove_member(h.cohort_id, team_id, a, actor_id=ACTOR)
    assert removed.member_ids == [b]
    assert [s.id for s in await h.service.unassigned_students(h.cohort_id, PROJECT)] == [a]

    with pytest.raises(NotFoundError):
        await h.service.delete(new_id(), team_id, actor_id=ACTOR)
    h.teams.in_use.add(team_id)
    with pytest.raises(ConflictError):
        await h.service.delete(h.cohort_id, team_id, actor_id=ACTOR)
    h.teams.in_use.clear()
    await h.service.delete(h.cohort_id, team_id, actor_id=ACTOR)
    assert await h.service.list_by_cohort(h.cohort_id, None) == []
    actions = [log.action for log in h.audit_logs.logs]
    assert actions[0] == "mentoring.team.create"
    assert actions[-1] == "mentoring.team.delete"


async def test_my_teams(h: Harness) -> None:
    user_id = new_id()
    student = h.students.add(h.cohort_id, user_id=user_id)
    await h.create(student.id)
    mine = await h.service.mine(user_id)
    assert [t.member_ids for t in mine.as_student] == [[student.id]]
    assert mine.as_mentor == []
    as_mentor = await h.service.mine(h.mentor.user_id)
    assert len(as_mentor.as_mentor) == 1
    students = await h.service.students_of(as_mentor.as_mentor)
    assert list(students) == [student.id]

from datetime import UTC, date, datetime

import pytest

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.registration_service import StaffRegistrationService
from app.contexts.organization.domain.entities import (
    BootcampTeam,
    CohortStaff,
    Department,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import (
    AssignmentScope,
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.shared.errors import BusinessRuleViolation, ConflictError, PermissionDeniedError
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.organization import (
    FakeStaffTargetCatalog,
    InMemoryBootcampTeamRepository,
    InMemoryCohortStaffRepository,
    InMemoryDepartmentRepository,
    InMemoryEmployeePositionRepository,
    InMemoryEmployeeRegistrationRepository,
    InMemoryTeamRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


class Harness:
    def __init__(self) -> None:
        self.department = Department(name="교육운영본부", description="교육 운영")
        self.team = Team(department_id=self.department.id, name="교육 1팀")
        self.other_team = Team(department_id=new_id(), name="다른 본부 팀")
        self.position = EmployeePosition(
            name="조교", priority=3, assignment_scope=AssignmentScope.COHORT
        )
        self.course_position = EmployeePosition(
            name="운영 매니저", priority=2, assignment_scope=AssignmentScope.COURSE
        )
        self.bootcamp = Bootcamp(hrd_net_bootcamp_id=new_id(), name="백엔드", code="AH")
        self.other_bootcamp = Bootcamp(hrd_net_bootcamp_id=new_id(), name="프론트", code="FE")
        self.cohort = Cohort(
            hrd_net_cohort_id=new_id(),
            bootcamp_id=self.bootcamp.id,
            cohort_number=3,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 4, 30),
        )
        self.registrations = InMemoryEmployeeRegistrationRepository()
        self.cohort_staffs = InMemoryCohortStaffRepository()
        self.service = StaffRegistrationService(
            registrations=self.registrations,
            departments=InMemoryDepartmentRepository(self.department),
            teams=InMemoryTeamRepository(self.team, self.other_team),
            bootcamp_teams=InMemoryBootcampTeamRepository(
                BootcampTeam(bootcamp_id=self.bootcamp.id, team_id=self.team.id)
            ),
            positions=InMemoryEmployeePositionRepository(self.position, self.course_position),
            cohort_staffs=self.cohort_staffs,
            catalog=FakeStaffTargetCatalog([self.bootcamp, self.other_bootcamp], [self.cohort]),
            uow=FakeUnitOfWork(),
            staff_email_domain="nextrunners.co.kr",
        )

    async def submit(self, user: User, **overrides: object) -> EmployeeRegistration:
        values: dict[str, object] = {
            "department_id": self.department.id,
            "team_id": self.team.id,
            "position_id": self.position.id,
            "employment_type": EmploymentType.REGULAR,
            "assignments": [
                RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=self.cohort.id)
            ],
        }
        values.update(overrides)
        return await self.service.submit(user, **values)  # type: ignore[arg-type]


def staff(**overrides: object) -> User:
    return make_user(email=f"staff{new_id().hex[-12:]}@nextrunners.co.kr", **overrides)


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_options_list_all_choices(h: Harness) -> None:
    options = await h.service.options(staff())
    assert [d.id for d in options.departments] == [h.department.id]
    assert {t.id for t in options.teams} == {h.team.id, h.other_team.id}
    assert options.bootcamp_teams == [BootcampTeam(bootcamp_id=h.bootcamp.id, team_id=h.team.id)]
    assert [p.id for p in options.positions] == [h.course_position.id, h.position.id]
    assert [b.id for b in options.bootcamps] == [h.bootcamp.id, h.other_bootcamp.id]
    assert [c.id for c in options.cohorts] == [h.cohort.id]


async def test_submit_then_update_pending_registration(h: Harness) -> None:
    user = staff()
    first = await h.submit(user)
    assert first.status is EmployeeRegistrationStatus.PENDING

    manager = RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=h.bootcamp.id)
    second = await h.submit(
        user,
        position_id=h.course_position.id,
        employment_type=EmploymentType.CONTRACT,
        assignments=[manager],
    )

    assert second.id == first.id  # 대기 중이면 같은 신청을 고친다
    assert len(h.registrations.items) == 1
    mine = await h.service.get_mine(user)
    assert mine is not None
    assert (mine.employment_type, mine.assignments) == (EmploymentType.CONTRACT, [manager])


async def test_rejected_registration_gets_new_one(h: Harness) -> None:
    user = staff()
    rejected = EmployeeRegistration(
        user_id=user.id,
        department_id=h.department.id,
        position_id=h.position.id,
        employment_type=EmploymentType.REGULAR,
        status=EmployeeRegistrationStatus.REJECTED,
        reviewed_at=NOW,
        reject_reason="담당 확인 필요",
    )
    await h.registrations.add(rejected)

    retry = await h.submit(user)

    assert retry.id != rejected.id
    assert retry.is_pending
    assert len(h.registrations.items) == 2


async def test_non_staff_account_is_rejected(h: Harness) -> None:
    student = make_user(email="kim@gmail.com")
    for call in (h.service.options(student), h.service.get_mine(student), h.submit(student)):
        with pytest.raises(PermissionDeniedError) as exc:
            await call
        assert exc.value.code == "not_staff_account"


async def test_approved_user_cannot_submit(h: Harness) -> None:
    user = staff()
    user.approve(now=NOW)
    with pytest.raises(ConflictError) as exc:
        await h.submit(user)
    assert exc.value.code == "user_already_approved"


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("department_id", "department_not_found"),
        ("team_id", "team_not_found"),
        ("position_id", "position_not_found"),
    ],
)
async def test_unknown_department_team_or_position(h: Harness, field: str, code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(staff(), **{field: new_id()})
    assert exc.value.code == code


async def test_unstaffable_target_is_rejected(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(
            staff(), assignments=[RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=new_id())]
        )
    assert exc.value.code == "invalid_staff_target"
    assert h.registrations.items == {}


async def test_team_must_belong_to_department(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(staff(), team_id=h.other_team.id, assignments=[])
    assert exc.value.code == "team_not_in_department"


async def test_department_direct_staff_without_team(h: Harness) -> None:
    """팀 없이 부서 직속으로 신청할 수 있다. 팀이 없으면 담당을 고를 수 없다 (A62)."""
    registration = await h.submit(staff(), team_id=None, assignments=[])
    assert registration.team_id is None
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(staff(), team_id=None)
    assert exc.value.code == "invalid_staff_assignment"


async def test_assignment_must_follow_position_scope(h: Harness) -> None:
    """COURSE 직위는 소속 팀의 과정만 운영 매니저로 고른다 (A62)."""
    other = RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=h.other_bootcamp.id)
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(staff(), position_id=h.course_position.id, assignments=[other])
    assert exc.value.code == "invalid_staff_assignment"
    with pytest.raises(BusinessRuleViolation):
        await h.submit(staff(), position_id=h.course_position.id)  # 조교 담당을 고름
    assert h.registrations.items == {}


async def test_cohort_with_assistant_is_hidden_and_rejected(h: Harness) -> None:
    """승인된 조교가 있는 기수는 선택지에서 빠지고 신청하면 거부된다 (A63)."""
    await h.cohort_staffs.add(
        CohortStaff(employee_id=new_id(), cohort_id=h.cohort.id, role=StaffRole.ASSISTANT)
    )
    assert (await h.service.options(staff())).cohorts == []
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.submit(staff())
    assert exc.value.code == "invalid_staff_assignment"
    assert h.registrations.items == {}


async def test_manager_on_cohort_does_not_hide_it(h: Harness) -> None:
    await h.cohort_staffs.add(
        CohortStaff(employee_id=new_id(), cohort_id=h.cohort.id, role=StaffRole.MANAGER)
    )
    assert [c.id for c in (await h.service.options(staff())).cohorts] == [h.cohort.id]
    assert (await h.submit(staff())).is_pending

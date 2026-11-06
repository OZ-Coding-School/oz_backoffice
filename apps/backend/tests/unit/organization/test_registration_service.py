from datetime import UTC, date, datetime

import pytest

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.registration_service import StaffRegistrationService
from app.contexts.organization.domain.entities import Department, EmployeePosition
from app.contexts.organization.domain.enums import (
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
    InMemoryDepartmentRepository,
    InMemoryEmployeePositionRepository,
    InMemoryEmployeeRegistrationRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


class Harness:
    def __init__(self) -> None:
        self.department = Department(name="교육 1팀", description="부트캠프 운영")
        self.position = EmployeePosition(name="매니저", priority=3)
        self.bootcamp = Bootcamp(hrd_net_bootcamp_id=new_id(), name="백엔드", code="AH")
        self.cohort = Cohort(
            hrd_net_cohort_id=new_id(),
            bootcamp_id=self.bootcamp.id,
            cohort_number=3,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 4, 30),
        )
        self.registrations = InMemoryEmployeeRegistrationRepository()
        self.service = StaffRegistrationService(
            registrations=self.registrations,
            departments=InMemoryDepartmentRepository(self.department),
            positions=InMemoryEmployeePositionRepository(self.position),
            catalog=FakeStaffTargetCatalog([self.bootcamp], [self.cohort]),
            uow=FakeUnitOfWork(),
            staff_email_domain="nextrunners.co.kr",
        )

    async def submit(self, user: User, **overrides: object) -> EmployeeRegistration:
        values: dict[str, object] = {
            "department_id": self.department.id,
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
    assert [p.id for p in options.positions] == [h.position.id]
    assert [b.id for b in options.bootcamps] == [h.bootcamp.id]
    assert [c.id for c in options.cohorts] == [h.cohort.id]


async def test_submit_then_update_pending_registration(h: Harness) -> None:
    user = staff()
    first = await h.submit(user)
    assert first.status is EmployeeRegistrationStatus.PENDING

    manager = RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=h.bootcamp.id)
    second = await h.submit(user, employment_type=EmploymentType.CONTRACT, assignments=[manager])

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
        ("position_id", "position_not_found"),
    ],
)
async def test_unknown_department_or_position(h: Harness, field: str, code: str) -> None:
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

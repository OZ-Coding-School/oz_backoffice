from datetime import UTC, datetime

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.infrastructure.repositories import (
    TortoiseEmployeeRegistrationRepository,
)
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.factories.organization import create_department, create_position

pytestmark = pytest.mark.integration


async def _registration(**overrides: object) -> EmployeeRegistration:
    user = make_user(email=f"staff{datetime.now(UTC).timestamp()}@nextrunners.co.kr")
    await TortoiseUserRepository().add(user)
    values: dict[str, object] = {
        "user_id": user.id,
        "department_id": (await create_department()).id,
        "position_id": (await create_position()).id,
        "employment_type": EmploymentType.REGULAR,
    }
    values.update(overrides)
    return EmployeeRegistration(**values)  # type: ignore[arg-type]


async def test_registration_round_trip_with_assignments() -> None:
    cohort = await create_cohort()
    assignments = [
        RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=cohort.bootcamp_id),
        RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort.id),
    ]
    registration = await _registration(assignments=assignments)
    repo = TortoiseEmployeeRegistrationRepository()
    await repo.add(registration)

    loaded = await repo.get(registration.id)
    assert loaded is not None
    assert loaded.assignments == assignments
    assert loaded.status is EmployeeRegistrationStatus.PENDING
    assert loaded.created_at is not None

    loaded.update(
        department_id=loaded.department_id,
        position_id=loaded.position_id,
        employment_type=EmploymentType.CONTRACT,
        assignments=assignments[1:],
    )
    await repo.save(loaded)
    latest = await repo.get_latest_by_user(registration.user_id)
    assert latest is not None
    assert latest.employment_type is EmploymentType.CONTRACT
    assert latest.assignments == assignments[1:]
    assert await repo.get_latest_by_user(make_user().id) is None


async def test_only_one_pending_registration_per_user() -> None:
    repo = TortoiseEmployeeRegistrationRepository()
    first = await _registration()
    await repo.add(first)
    duplicate = await _registration(user_id=first.user_id)
    with pytest.raises(IntegrityError, match="uid_employee_registrations_pending_user"):
        await repo.add(duplicate)


async def test_rejected_registration_allows_new_one_and_latest_wins() -> None:
    repo = TortoiseEmployeeRegistrationRepository()
    rejected = await _registration(
        status=EmployeeRegistrationStatus.REJECTED,
        reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
        reject_reason="부서 확인 필요",
    )
    await repo.add(rejected)
    retry = await _registration(user_id=rejected.user_id)
    await repo.add(retry)

    latest = await repo.get_latest_by_user(rejected.user_id)
    assert latest is not None
    assert latest.id == retry.id


@pytest.mark.parametrize(
    ("sql", "constraint"),
    [
        (
            "UPDATE employee_registrations SET status = 'APPROVED'",
            "check_employee_registrations_reviewed",
        ),
        (
            "UPDATE employee_registrations SET reject_reason = 'x'",
            "check_employee_registrations_reject_reason",
        ),
        (
            "UPDATE employee_registrations SET employment_type = 'UNKNOWN'",
            "check_employee_registrations_employment_type",
        ),
        (
            "INSERT INTO employee_registration_assignments (id, registration_id, role) "
            "VALUES (gen_random_uuid(), "
            "(SELECT id FROM employee_registrations LIMIT 1), 'MANAGER')",
            "check_employee_registration_assignments_target",
        ),
        (
            "INSERT INTO employee_registration_assignments (id, registration_id, role, cohort_id) "
            "SELECT gen_random_uuid(), registration_id, role, cohort_id "
            "FROM employee_registration_assignments",
            "uid_employee_registration_assignments_target",
        ),
    ],
)
async def test_db_constraints(sql: str, constraint: str) -> None:
    cohort = await create_cohort()
    registration = await _registration(
        assignments=[RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort.id)]
    )
    await TortoiseEmployeeRegistrationRepository().add(registration)
    with pytest.raises(IntegrityError, match=constraint):
        await connections.get("default").execute_query(sql)


async def test_list_by_status_with_paging() -> None:
    repo = TortoiseEmployeeRegistrationRepository()
    pending = []
    for _ in range(3):
        registration = await _registration()
        await repo.add(registration)
        pending.append(registration.id)
    rejected = await _registration(
        status=EmployeeRegistrationStatus.REJECTED,
        reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
        reject_reason="x",
    )
    await repo.add(rejected)

    page, total = await repo.list_by_status(EmployeeRegistrationStatus.PENDING, limit=2, offset=1)
    assert total == 3
    assert [r.id for r in page] == pending[1:]
    rejected_page, rejected_total = await repo.list_by_status(
        EmployeeRegistrationStatus.REJECTED, limit=10, offset=0
    )
    assert (rejected_total, [r.id for r in rejected_page]) == (1, [rejected.id])

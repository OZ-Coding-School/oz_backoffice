from datetime import UTC, datetime

import pytest

from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.employee_queries import EmployeeQueries
from app.contexts.organization.application.staff_service import StaffTarget
from app.contexts.organization.domain.enums import StaffRole
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
)
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.organization import create_employee
from tests.factories.staff_review import build_staff_service, create_applicant

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


@pytest.fixture
async def actor() -> User:
    return await create_applicant()


async def _scope(user_id: object) -> set[tuple[str, object]]:
    """담당 배정 = 데이터 범위 (A87)."""
    access = await EmployeeQueries(
        TortoiseEmployeeRepository(),
        positions=TortoiseEmployeePositionRepository(),
        bootcamp_staffs=TortoiseBootcampStaffRepository(),
        cohort_staffs=TortoiseCohortStaffRepository(),
    ).access_of(user_id)  # type: ignore[arg-type]
    if access is None:
        return set()
    return {("BOOTCAMP", b) for b in access.bootcamp_ids} | {
        ("COHORT", c) for c in access.cohort_ids
    }


async def test_assign_and_unassign_cohort_staff_changes_scope(actor: User) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    service = build_staff_service()

    member = await service.assign(
        StaffTarget.COHORT,
        cohort.id,
        employee_id=employee.id,
        role=StaffRole.ASSISTANT,
        actor_id=actor.id,
    )

    assert (member.user_id, member.role) == (employee.user_id, StaffRole.ASSISTANT)
    assert [m.id for m in await service.list_members(StaffTarget.COHORT, cohort.id)] == [member.id]
    assert await _scope(employee.user_id) == {("COHORT", cohort.id)}

    await service.unassign(StaffTarget.COHORT, cohort.id, member.id, actor_id=actor.id)

    assert await service.list_members(StaffTarget.COHORT, cohort.id) == []
    assert await _scope(employee.user_id) == set()
    logs = await AuditLogModel.filter(target_id=cohort.id).order_by("created_at")
    assert [log.action for log in logs] == [
        "organization.staff.assign",
        "organization.staff.unassign",
    ]


async def test_bootcamp_staff_and_independent_scope(actor: User) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    service = build_staff_service()
    await service.assign(
        StaffTarget.BOOTCAMP,
        cohort.bootcamp_id,
        employee_id=employee.id,
        role=StaffRole.MANAGER,
        actor_id=actor.id,
    )
    cohort_member = await service.assign(
        StaffTarget.COHORT,
        cohort.id,
        employee_id=employee.id,
        role=StaffRole.MANAGER,
        actor_id=actor.id,
    )

    # 기수 담당을 해제해도 과정 담당은 남는다
    await service.unassign(StaffTarget.COHORT, cohort.id, cohort_member.id, actor_id=actor.id)
    assert await _scope(employee.user_id) == {("BOOTCAMP", cohort.bootcamp_id)}


async def test_assign_errors(actor: User) -> None:
    cohort = await create_cohort()
    employee = await create_employee()
    service = build_staff_service()
    await service.assign(
        StaffTarget.COHORT,
        cohort.id,
        employee_id=employee.id,
        role=StaffRole.ASSISTANT,
        actor_id=actor.id,
    )

    with pytest.raises(ConflictError) as conflict:
        await service.assign(
            StaffTarget.COHORT,
            cohort.id,
            employee_id=employee.id,
            role=StaffRole.ASSISTANT,
            actor_id=actor.id,
        )
    assert conflict.value.code == "staff_already_assigned"
    with pytest.raises(NotFoundError) as missing:
        await service.assign(
            StaffTarget.COHORT,
            cohort.id,
            employee_id=new_id(),
            role=StaffRole.MANAGER,
            actor_id=actor.id,
        )
    assert missing.value.code == "employee_not_found"
    with pytest.raises(BusinessRuleViolation) as target:
        await service.assign(
            StaffTarget.COHORT,
            new_id(),
            employee_id=employee.id,
            role=StaffRole.MANAGER,
            actor_id=actor.id,
        )
    assert target.value.code == "invalid_staff_target"
    with pytest.raises(NotFoundError) as staff:
        await service.unassign(StaffTarget.COHORT, cohort.id, new_id(), actor_id=actor.id)
    assert staff.value.code == "staff_not_found"
    # 다른 기수의 담당자 ID로는 해제할 수 없다
    member = (await service.list_members(StaffTarget.COHORT, cohort.id))[0]
    with pytest.raises(NotFoundError):
        await service.unassign(
            StaffTarget.COHORT, (await create_cohort()).id, member.id, actor_id=actor.id
        )

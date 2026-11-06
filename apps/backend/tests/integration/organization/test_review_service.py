from datetime import UTC, datetime

import pytest

from app.contexts.access.domain.catalog import COHORT_ASSISTANT, COHORT_MANAGER
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import UserApprovalStatus
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.application.review_service import RegistrationAdjustment
from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import RequestedAssignment
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
    TortoiseEmployeeRepository,
)
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.organization import create_department
from tests.factories.staff_review import (
    build_review_service,
    create_applicant,
    create_registration,
    seed_roles,
)

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


@pytest.fixture
async def actor() -> User:
    """검토하는 어드민 (감사 로그 처리자 FK)."""
    return await create_applicant()


async def _roles(user_id: object) -> set[tuple[str, str, object]]:
    grants = await TortoiseUserRoleRepository().list_grants(user_id, now=NOW)  # type: ignore[arg-type]
    return {(g.role_code, g.scope_type.value, g.scope_id) for g in grants}


async def test_approve_creates_employee_staffs_roles_and_approves_user() -> None:
    await seed_roles()
    cohort = await create_cohort()
    applicant = await create_applicant()
    registration = await create_registration(
        applicant,
        [
            RequestedAssignment(role=StaffRole.MANAGER, bootcamp_id=cohort.bootcamp_id),
            RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort.id),
        ],
    )
    admin = await create_applicant()

    approved = await build_review_service().approve(registration.id, actor_id=admin.id)

    assert approved.status is EmployeeRegistrationStatus.APPROVED
    employee = await TortoiseEmployeeRepository().get_by_user(applicant.id)
    assert employee is not None
    assert employee.department_id == registration.department_id
    bootcamp_staffs = await TortoiseBootcampStaffRepository().list_by_employee(employee.id)
    cohort_staffs = await TortoiseCohortStaffRepository().list_by_employee(employee.id)
    assert [(s.bootcamp_id, s.role) for s in bootcamp_staffs] == [
        (cohort.bootcamp_id, StaffRole.MANAGER)
    ]
    assert [(s.cohort_id, s.role) for s in cohort_staffs] == [(cohort.id, StaffRole.ASSISTANT)]
    assert await _roles(applicant.id) == {
        (COHORT_MANAGER, "BOOTCAMP", cohort.bootcamp_id),
        (COHORT_ASSISTANT, "COHORT", cohort.id),
    }
    user = await TortoiseUserRepository().get(applicant.id)
    assert user is not None
    assert user.approval_status is UserApprovalStatus.APPROVED
    assert user.is_active
    log = await AuditLogModel.get(target_id=registration.id)
    assert log.action == "organization.staff_registration.approve"
    assert log.actor_user_id == admin.id  # type: ignore[attr-defined]  # FK 컬럼 속성


async def test_approve_with_adjustment(actor: User) -> None:
    await seed_roles()
    cohort = await create_cohort()
    applicant = await create_applicant()
    registration = await create_registration(
        applicant, [RequestedAssignment(role=StaffRole.MANAGER, cohort_id=cohort.id)]
    )
    other_department = await create_department()

    approved = await build_review_service().approve(
        registration.id,
        actor_id=actor.id,
        adjustment=RegistrationAdjustment(
            department_id=other_department.id,
            employment_type=EmploymentType.CONTRACT,
            assignments=[RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort.id)],
        ),
    )

    assert approved.department_id == other_department.id
    assert approved.position_id == registration.position_id  # 조정하지 않은 항목은 신청값
    employee = await TortoiseEmployeeRepository().get_by_user(applicant.id)
    assert employee is not None
    assert (employee.department_id, employee.employment_type) == (
        other_department.id,
        EmploymentType.CONTRACT,
    )
    assert await _roles(applicant.id) == {(COHORT_ASSISTANT, "COHORT", cohort.id)}
    log = await AuditLogModel.get(target_id=registration.id)
    assert log.before["assignments"][0]["role"] == "MANAGER"  # type: ignore[index]
    assert log.after["assignments"][0]["role"] == "ASSISTANT"  # type: ignore[index]


async def test_second_approval_updates_employee_and_skips_existing_staff(actor: User) -> None:
    await seed_roles()
    cohort = await create_cohort()
    applicant = await create_applicant()
    same = [RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=cohort.id)]
    service = build_review_service()
    await service.approve((await create_registration(applicant, same)).id, actor_id=actor.id)
    second = await create_registration(applicant, same)

    await service.approve(second.id, actor_id=actor.id)

    employee = await TortoiseEmployeeRepository().get_by_user(applicant.id)
    assert employee is not None
    assert employee.department_id == second.department_id
    assert len(await TortoiseCohortStaffRepository().list_by_employee(employee.id)) == 1
    assert len(await _roles(applicant.id)) == 1


async def test_invalid_adjustment_rolls_back_everything(actor: User) -> None:
    await seed_roles()
    applicant = await create_applicant()
    registration = await create_registration(applicant)
    with pytest.raises(BusinessRuleViolation) as exc:
        await build_review_service().approve(
            registration.id,
            actor_id=actor.id,
            adjustment=RegistrationAdjustment(
                assignments=[RequestedAssignment(role=StaffRole.ASSISTANT, cohort_id=new_id())]
            ),
        )
    assert exc.value.code == "invalid_staff_target"
    reloaded = await build_review_service().get(registration.id)
    assert reloaded.is_pending
    assert await TortoiseEmployeeRepository().get_by_user(applicant.id) is None


async def test_reject_marks_pending_user_rejected(actor: User) -> None:
    applicant = await create_applicant()
    registration = await create_registration(applicant)

    rejected = await build_review_service().reject(
        registration.id, actor_id=actor.id, reason="부서를 다시 확인해 주세요"
    )

    assert rejected.status is EmployeeRegistrationStatus.REJECTED
    user = await TortoiseUserRepository().get(applicant.id)
    assert user is not None
    assert user.approval_status is UserApprovalStatus.REJECTED
    log = await AuditLogModel.get(target_id=registration.id)
    assert log.after == {"reason": "부서를 다시 확인해 주세요"}


async def test_reject_keeps_already_approved_user(actor: User) -> None:
    applicant = await create_applicant()
    approved_user = await TortoiseUserRepository().get(applicant.id)
    assert approved_user is not None
    approved_user.approve(now=NOW)
    await TortoiseUserRepository().save(approved_user)
    registration = await create_registration(applicant)

    await build_review_service().reject(registration.id, actor_id=actor.id, reason="중복 신청")

    user = await TortoiseUserRepository().get(applicant.id)
    assert user is not None
    assert user.is_approved


async def test_review_errors(actor: User) -> None:
    service = build_review_service()
    with pytest.raises(NotFoundError):
        await service.approve(new_id(), actor_id=actor.id)
    registration = await create_registration(await create_applicant())
    await service.reject(registration.id, actor_id=actor.id, reason="x")
    with pytest.raises(BusinessRuleViolation) as exc:
        await service.approve(registration.id, actor_id=actor.id)
    assert exc.value.code == "registration_not_pending"

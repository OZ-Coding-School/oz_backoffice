"""운영진 가입 신청 검토·담당자 배정 테스트용 서비스 조립과 데이터 빌더 (실제 DB)."""

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.application.registration_service import (
    RegistrationChoiceValidator,
)
from app.contexts.organization.application.review_service import StaffRegistrationReviewService
from app.contexts.organization.application.staff_service import StaffAssignmentService
from app.contexts.organization.domain.enums import EmploymentType
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseBootcampTeamRepository,
    TortoiseCohortStaffRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRegistrationRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.factories.organization import create_department, create_position


def build_review_service() -> StaffRegistrationReviewService:
    clock = SystemClock()
    return StaffRegistrationReviewService(
        registrations=TortoiseEmployeeRegistrationRepository(),
        employees=TortoiseEmployeeRepository(),
        bootcamp_staffs=TortoiseBootcampStaffRepository(),
        cohort_staffs=TortoiseCohortStaffRepository(),
        validator=RegistrationChoiceValidator(
            departments=TortoiseDepartmentRepository(),
            teams=TortoiseTeamRepository(),
            bootcamp_teams=TortoiseBootcampTeamRepository(),
            positions=TortoiseEmployeePositionRepository(),
            catalog=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        ),
        users=UserAdministration(TortoiseUserRepository(), clock),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


async def create_applicant(**overrides: object) -> User:
    user = make_user(email=f"staff{new_id().hex[-12:]}@nextrunners.co.kr", **overrides)
    await TortoiseUserRepository().add(user)
    return user


async def create_registration(
    user: User, assignments: list[RequestedAssignment] | None = None
) -> EmployeeRegistration:
    registration = EmployeeRegistration(
        user_id=user.id,
        department_id=(await create_department()).id,
        position_id=(await create_position()).id,
        employment_type=EmploymentType.REGULAR,
        assignments=assignments or [],
    )
    await TortoiseEmployeeRegistrationRepository().add(registration)
    return registration


def build_staff_service() -> StaffAssignmentService:
    clock = SystemClock()
    return StaffAssignmentService(
        employees=TortoiseEmployeeRepository(),
        bootcamp_staffs=TortoiseBootcampStaffRepository(),
        cohort_staffs=TortoiseCohortStaffRepository(),
        catalog=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
    )

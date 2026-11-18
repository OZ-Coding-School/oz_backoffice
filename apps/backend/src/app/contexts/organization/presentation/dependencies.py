"""organization 서비스 조립."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.organization.application.org_service import (
    BootcampLookup,
    OrganizationAdminService,
)
from app.contexts.organization.application.registration_service import (
    RegistrationChoiceValidator,
    StaffRegistrationService,
    StaffTargetCatalog,
)
from app.contexts.organization.application.review_service import (
    StaffRegistrationReviewService,
    StaffUserApprover,
)
from app.contexts.organization.application.staff_roles import StaffRoleGranter, StaffRoleSync
from app.contexts.organization.application.staff_service import StaffAssignmentService
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
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock
from app.core.uow import UnitOfWork


def get_staff_target_catalog(request: Request) -> StaffTargetCatalog:
    """academy 공개 서비스. app.main이 app.state에 연결한다 (decisions B10)."""
    return cast("StaffTargetCatalog", request.app.state.academy_catalog)


def get_staff_registration_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
    catalog: Annotated[StaffTargetCatalog, Depends(get_staff_target_catalog)],
) -> StaffRegistrationService:
    return StaffRegistrationService(
        registrations=TortoiseEmployeeRegistrationRepository(),
        departments=TortoiseDepartmentRepository(),
        teams=TortoiseTeamRepository(),
        bootcamp_teams=TortoiseBootcampTeamRepository(),
        positions=TortoiseEmployeePositionRepository(),
        cohort_staffs=TortoiseCohortStaffRepository(),
        catalog=catalog,
        uow=UnitOfWork(),
        staff_email_domain=settings.google_allowed_domain,
    )


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


def get_staff_registration_review_service(
    request: Request,
    catalog: Annotated[StaffTargetCatalog, Depends(get_staff_target_catalog)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> StaffRegistrationReviewService:
    """회원 승인(identity)·역할 부여(access)·감사 로그(audit)는
    app.main이 app.state에 연결한 공개 서비스를 쓴다 (decisions B10).
    """
    state = request.app.state
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
            catalog=catalog,
        ),
        users=cast("StaffUserApprover", state.user_admin),
        roles=cast("StaffRoleGranter", state.role_assignments),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


def get_staff_assignment_service(
    request: Request,
    catalog: Annotated[StaffTargetCatalog, Depends(get_staff_target_catalog)],
) -> StaffAssignmentService:
    state = request.app.state
    return StaffAssignmentService(
        employees=TortoiseEmployeeRepository(),
        bootcamp_staffs=TortoiseBootcampStaffRepository(),
        cohort_staffs=TortoiseCohortStaffRepository(),
        catalog=catalog,
        roles=cast("StaffRoleSync", state.role_assignments),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
    )


def get_organization_admin_service(request: Request) -> OrganizationAdminService:
    return OrganizationAdminService(
        departments=TortoiseDepartmentRepository(),
        teams=TortoiseTeamRepository(),
        bootcamp_teams=TortoiseBootcampTeamRepository(),
        bootcamps=cast("BootcampLookup", request.app.state.academy_catalog),
        positions=TortoiseEmployeePositionRepository(),
        employees=TortoiseEmployeeRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )

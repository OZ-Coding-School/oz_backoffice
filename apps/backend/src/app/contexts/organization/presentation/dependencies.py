"""organization 서비스 조립."""

from typing import Annotated, cast

from fastapi import Depends, Request

from app.contexts.organization.application.registration_service import (
    StaffRegistrationService,
    StaffTargetCatalog,
)
from app.contexts.organization.infrastructure.repositories import (
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRegistrationRepository,
)
from app.core.config import Settings
from app.core.dependencies import get_app_settings
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
        positions=TortoiseEmployeePositionRepository(),
        catalog=catalog,
        uow=UnitOfWork(),
        staff_email_domain=settings.google_allowed_domain,
    )

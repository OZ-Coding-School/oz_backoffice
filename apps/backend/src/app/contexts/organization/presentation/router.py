"""운영진 최초 정보 입력 API (/me/staff-registration).

승인 전(PENDING)에도 호출할 수 있다 (`/me` 범위, plan §2.2). 운영진 도메인 계정만 쓸 수 있다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.contexts.access.presentation.dependencies import CurrentUser
from app.contexts.organization.application.registration_service import StaffRegistrationService
from app.contexts.organization.domain.enums import EmploymentType, StaffRole
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.presentation.dependencies import get_staff_registration_service
from app.contexts.organization.presentation.schemas import (
    AssignmentPayload,
    BootcampOption,
    CohortOption,
    DepartmentOption,
    PositionOption,
    StaffRegistrationOptionsResponse,
    StaffRegistrationRequest,
    StaffRegistrationResponse,
    TeamOption,
)

router = APIRouter(prefix="/me/staff-registration", tags=["staff-registration"])

ServiceDep = Annotated[StaffRegistrationService, Depends(get_staff_registration_service)]


def to_registration_response(registration: EmployeeRegistration) -> StaffRegistrationResponse:
    return StaffRegistrationResponse(
        id=registration.id,
        status=registration.status,
        department_id=registration.department_id,
        team_id=registration.team_id,
        position_id=registration.position_id,
        employment_type=registration.employment_type,
        assignments=[
            AssignmentPayload(role=a.role, bootcamp_id=a.bootcamp_id, cohort_id=a.cohort_id)
            for a in registration.assignments
        ],
        reviewed_at=registration.reviewed_at,
        reject_reason=registration.reject_reason,
        created_at=registration.created_at,
    )


@router.get("/options", response_model=StaffRegistrationOptionsResponse)
async def registration_options(
    user: CurrentUser, service: ServiceDep
) -> StaffRegistrationOptionsResponse:
    """신청 선택지. 팀은 부서별로, 과정은 담당 팀(`team_id`)으로 거른다 (A62)."""
    options = await service.options(user)
    bootcamp_teams = {link.bootcamp_id: link.team_id for link in options.bootcamp_teams}
    return StaffRegistrationOptionsResponse(
        departments=[DepartmentOption(id=d.id, name=d.name) for d in options.departments],
        teams=[
            TeamOption(id=t.id, department_id=t.department_id, name=t.name) for t in options.teams
        ],
        positions=[
            PositionOption(id=p.id, name=p.name, assignment_scope=p.assignment_scope)
            for p in options.positions
        ],
        employment_types=list(EmploymentType),
        staff_roles=list(StaffRole),
        bootcamps=[
            BootcampOption(id=b.id, name=b.name, code=b.code, team_id=bootcamp_teams.get(b.id))
            for b in options.bootcamps
        ],
        cohorts=[
            CohortOption(
                id=c.id,
                bootcamp_id=c.bootcamp_id,
                cohort_number=c.cohort_number,
                status=c.status,
                start_date=c.start_date,
                end_date=c.end_date,
            )
            for c in options.cohorts
        ],
    )


@router.get("", response_model=StaffRegistrationResponse | None)
async def my_registration(
    user: CurrentUser, service: ServiceDep
) -> StaffRegistrationResponse | None:
    """가장 최근 신청. 아직 신청하지 않았으면 null."""
    registration = await service.get_mine(user)
    return to_registration_response(registration) if registration else None


@router.put("", response_model=StaffRegistrationResponse)
async def submit_registration(
    body: StaffRegistrationRequest, user: CurrentUser, service: ServiceDep
) -> StaffRegistrationResponse:
    """신청한다. 대기 중이면 내용을 고치고, 반려됐으면 새로 신청한다.

    팀은 부서 소속이어야 하고, 담당은 직위 담당 방식대로 소속 팀의 과정에서 고른다
    (위반 시 422 `team_not_in_department`·`invalid_staff_assignment`, A62).
    """
    registration = await service.submit(
        user,
        department_id=body.department_id,
        team_id=body.team_id,
        position_id=body.position_id,
        employment_type=body.employment_type,
        assignments=[
            RequestedAssignment(role=a.role, bootcamp_id=a.bootcamp_id, cohort_id=a.cohort_id)
            for a in body.assignments
        ],
    )
    return to_registration_response(registration)

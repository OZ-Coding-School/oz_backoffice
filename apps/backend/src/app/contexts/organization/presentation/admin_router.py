"""운영진 가입 신청 검토 API (/admin/staff-registrations).

권한: role.assign (전체 범위, SUPER_ADMIN).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.review_service import (
    RegistrationAdjustment,
    StaffRegistrationReviewService,
)
from app.contexts.organization.domain.enums import EmployeeRegistrationStatus
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
)
from app.contexts.organization.presentation.dependencies import (
    get_staff_registration_review_service,
    get_user_queries,
)
from app.contexts.organization.presentation.router import to_registration_response
from app.contexts.organization.presentation.schemas import (
    AdminStaffRegistrationResponse,
    ApplicantSummary,
    ApproveStaffRegistrationRequest,
    RejectStaffRegistrationRequest,
)
from app.core.pagination import Page

router = APIRouter(prefix="/admin/staff-registrations", tags=["admin-staff-registrations"])

Reviewer = Annotated[User, Depends(require_permission("role.assign"))]
ServiceDep = Annotated[
    StaffRegistrationReviewService, Depends(get_staff_registration_review_service)
]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]


async def _responses(
    registrations: list[EmployeeRegistration], users: UserQueries
) -> list[AdminStaffRegistrationResponse]:
    applicants = await users.get_many([r.user_id for r in registrations])
    responses = []
    for registration in registrations:
        applicant = applicants.get(registration.user_id)
        responses.append(
            AdminStaffRegistrationResponse(
                **to_registration_response(registration).model_dump(),
                applicant=ApplicantSummary(
                    id=applicant.id,
                    email=applicant.email,
                    name=applicant.name,
                    approval_status=applicant.approval_status,
                )
                if applicant
                else None,
            )
        )
    return responses


@router.get("", response_model=Page[AdminStaffRegistrationResponse])
async def list_staff_registrations(
    _: Reviewer,
    service: ServiceDep,
    users: UsersDep,
    status: EmployeeRegistrationStatus = EmployeeRegistrationStatus.PENDING,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminStaffRegistrationResponse]:
    """상태별 신청 목록 (기본: 승인 대기, 오래된 신청부터)."""
    registrations, total = await service.list_by_status(status, limit=limit, offset=offset)
    return Page(
        items=await _responses(registrations, users), total=total, limit=limit, offset=offset
    )


@router.get("/{registration_id}", response_model=AdminStaffRegistrationResponse)
async def get_staff_registration(
    registration_id: uuid.UUID, _: Reviewer, service: ServiceDep, users: UsersDep
) -> AdminStaffRegistrationResponse:
    return (await _responses([await service.get(registration_id)], users))[0]


@router.post("/{registration_id}/approve", response_model=AdminStaffRegistrationResponse)
async def approve_staff_registration(
    registration_id: uuid.UUID,
    reviewer: Reviewer,
    service: ServiceDep,
    users: UsersDep,
    body: ApproveStaffRegistrationRequest | None = None,
) -> AdminStaffRegistrationResponse:
    """승인. 본문으로 부서·팀·직위·고용 형태·담당을 조정할 수 있다 (보내지 않은 항목은 신청값)."""
    body = body or ApproveStaffRegistrationRequest()
    adjustment = RegistrationAdjustment(
        department_id=body.department_id,
        team_changed="team_id" in body.model_fields_set,
        team_id=body.team_id,
        position_id=body.position_id,
        employment_type=body.employment_type,
        assignments=None
        if body.assignments is None
        else [
            RequestedAssignment(role=a.role, bootcamp_id=a.bootcamp_id, cohort_id=a.cohort_id)
            for a in body.assignments
        ],
    )
    registration = await service.approve(
        registration_id, actor_id=reviewer.id, adjustment=adjustment
    )
    return (await _responses([registration], users))[0]


@router.post("/{registration_id}/reject", response_model=AdminStaffRegistrationResponse)
async def reject_staff_registration(
    registration_id: uuid.UUID,
    body: RejectStaffRegistrationRequest,
    reviewer: Reviewer,
    service: ServiceDep,
    users: UsersDep,
) -> AdminStaffRegistrationResponse:
    registration = await service.reject(registration_id, actor_id=reviewer.id, reason=body.reason)
    return (await _responses([registration], users))[0]

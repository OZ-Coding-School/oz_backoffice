"""과정·기수 담당자 관리 API. 권한: staff.assign (전체 범위, SUPER_ADMIN·TEAM_LEAD, decisions A36).

배정·해제하면 같은 트랜잭션에서 담당에 맞는 역할이 부여·회수된다 (decisions D4).
"""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.staff_service import (
    StaffAssignmentService,
    StaffMember,
    StaffTarget,
)
from app.contexts.organization.presentation.dependencies import (
    get_staff_assignment_service,
    get_user_queries,
)
from app.contexts.organization.presentation.schemas import (
    AssignStaffRequest,
    StaffMemberResponse,
    StaffUserSummary,
)

router = APIRouter(prefix="/admin", tags=["admin-staffs"])

Admin = Annotated[User, Depends(require_permission("staff.assignment.manage"))]
AdminReader = Annotated[User, Depends(require_permission("staff.assignment.read"))]
ServiceDep = Annotated[StaffAssignmentService, Depends(get_staff_assignment_service)]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]


async def _responses(
    members: Sequence[StaffMember], users: UserQueries
) -> list[StaffMemberResponse]:
    found = await users.get_many([m.user_id for m in members if m.user_id is not None])
    responses = []
    for member in members:
        user = found.get(member.user_id) if member.user_id else None
        responses.append(
            StaffMemberResponse(
                id=member.id,
                employee_id=member.employee_id,
                role=member.role,
                user=StaffUserSummary(id=user.id, email=user.email, name=user.name)
                if user
                else None,
                created_at=member.created_at,
            )
        )
    return responses


async def _assign(
    target: StaffTarget,
    target_id: uuid.UUID,
    body: AssignStaffRequest,
    admin: User,
    service: StaffAssignmentService,
    users: UserQueries,
) -> StaffMemberResponse:
    member = await service.assign(
        target, target_id, employee_id=body.employee_id, role=body.role, actor_id=admin.id
    )
    return (await _responses([member], users))[0]


# ---------------------------------------------------------------- 과정 담당자
@router.get("/bootcamps/{bootcamp_id}/staffs", response_model=list[StaffMemberResponse])
async def list_bootcamp_staffs(
    bootcamp_id: uuid.UUID, _: AdminReader, service: ServiceDep, users: UsersDep
) -> list[StaffMemberResponse]:
    return await _responses(await service.list_members(StaffTarget.BOOTCAMP, bootcamp_id), users)


@router.post(
    "/bootcamps/{bootcamp_id}/staffs",
    response_model=StaffMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_bootcamp_staff(
    bootcamp_id: uuid.UUID,
    body: AssignStaffRequest,
    admin: Admin,
    service: ServiceDep,
    users: UsersDep,
) -> StaffMemberResponse:
    """과정 담당자 배정. 과정 범위(BOOTCAMP) 역할을 함께 부여한다."""
    return await _assign(StaffTarget.BOOTCAMP, bootcamp_id, body, admin, service, users)


@router.delete("/bootcamps/{bootcamp_id}/staffs/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_bootcamp_staff(
    bootcamp_id: uuid.UUID, staff_id: uuid.UUID, admin: Admin, service: ServiceDep
) -> Response:
    """과정 담당자 해제. 대응하는 역할을 함께 회수한다."""
    await service.unassign(StaffTarget.BOOTCAMP, bootcamp_id, staff_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 기수 담당자
@router.get("/cohorts/{cohort_id}/staffs", response_model=list[StaffMemberResponse])
async def list_cohort_staffs(
    cohort_id: uuid.UUID, _: AdminReader, service: ServiceDep, users: UsersDep
) -> list[StaffMemberResponse]:
    return await _responses(await service.list_members(StaffTarget.COHORT, cohort_id), users)


@router.post(
    "/cohorts/{cohort_id}/staffs",
    response_model=StaffMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_cohort_staff(
    cohort_id: uuid.UUID,
    body: AssignStaffRequest,
    admin: Admin,
    service: ServiceDep,
    users: UsersDep,
) -> StaffMemberResponse:
    """기수 담당자 배정. 기수 범위(COHORT) 역할을 함께 부여한다."""
    return await _assign(StaffTarget.COHORT, cohort_id, body, admin, service, users)


@router.delete("/cohorts/{cohort_id}/staffs/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_cohort_staff(
    cohort_id: uuid.UUID, staff_id: uuid.UUID, admin: Admin, service: ServiceDep
) -> Response:
    """기수 담당자 해제. 대응하는 역할을 함께 회수한다."""
    await service.unassign(StaffTarget.COHORT, cohort_id, staff_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

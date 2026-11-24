"""운영진 유효 권한·담당 기수 (GET /me/staff-access, decisions F17·A81, BE-3).

운영진(STAFF)만 부른다. 수강생·멘토는 403 `staff_only`.
"""

import uuid
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.contexts.access.application.grant_source import EmployeeAccessDirectory
from app.contexts.access.application.staff_access import ScopedCohortCatalog, StaffAccessQueries
from app.contexts.access.presentation.dependencies import ApprovedUser, PermissionCheckerDep
from app.contexts.identity.domain.enums import AccountType
from app.shared.errors import PermissionDeniedError

router = APIRouter(prefix="/me/staff-access", tags=["me-staff-access"])


class PermissionScopeResponse(BaseModel):
    code: str = Field(description="권한 코드 (access/domain/catalog.py)")
    is_global: bool = Field(description="전체 범위")
    bootcamp_ids: list[uuid.UUID] = Field(description="과정 범위 (그 과정의 기수 전부)")
    cohort_ids: list[uuid.UUID] = Field(description="기수 범위")


class StaffCohortResponse(BaseModel):
    id: uuid.UUID
    bootcamp_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int
    start_date: date
    end_date: date
    status: str = Field(description="ONGOING·PLANNED·ENDED·INACTIVE (보관은 없음)")


class StaffPositionResponse(BaseModel):
    id: uuid.UUID
    name: str
    all_data: bool = Field(description="데이터 범위가 전체인지 (아니면 담당 과정·기수만)")


class StaffAccessResponse(BaseModel):
    is_super_admin: bool = Field(description="최고 관리자 (모든 권한·모든 데이터, A87)")
    position: StaffPositionResponse | None = Field(description="직위 (= 역할). 직원이 아니면 없음")
    permissions: list[PermissionScopeResponse] = Field(description="가진 권한만")
    cohorts: list[StaffCohortResponse] = Field(
        description="권한이 미치는 기수. 진행 중 → 예정 → 종료 → 비활성, 최근 시작 순 (A81)"
    )


def get_cohort_catalog(request: Request) -> ScopedCohortCatalog:
    return cast("ScopedCohortCatalog", request.app.state.academy_catalog)


def get_employee_access(request: Request) -> EmployeeAccessDirectory:
    return cast("EmployeeAccessDirectory", request.app.state.employee_queries)


@router.get("", response_model=StaffAccessResponse)
async def my_staff_access(
    user: ApprovedUser,
    checker: PermissionCheckerDep,
    cohorts: Annotated[ScopedCohortCatalog, Depends(get_cohort_catalog)],
    employees: Annotated[EmployeeAccessDirectory, Depends(get_employee_access)],
) -> StaffAccessResponse:
    if user.account_type is not AccountType.STAFF:
        raise PermissionDeniedError("운영진만 볼 수 있습니다.", code="staff_only")
    access = await StaffAccessQueries(checker, cohorts).of(user.id)
    employee = await employees.access_of(user.id)
    return StaffAccessResponse(
        is_super_admin=user.is_super_admin,
        position=StaffPositionResponse(
            id=employee.position_id, name=employee.position_name, all_data=employee.all_data
        )
        if employee
        else None,
        permissions=[
            PermissionScopeResponse(
                code=code,
                is_global=scope.is_global,
                bootcamp_ids=sorted(scope.bootcamp_ids),
                cohort_ids=sorted(scope.cohort_ids),
            )
            for code, scope in access.permissions.items()
        ],
        cohorts=[
            StaffCohortResponse(
                id=c.id,
                bootcamp_id=c.bootcamp_id,
                bootcamp_name=c.bootcamp_name,
                cohort_number=c.cohort_number,
                start_date=c.start_date,
                end_date=c.end_date,
                status=str(c.status),
            )
            for c in access.cohorts
        ],
    )

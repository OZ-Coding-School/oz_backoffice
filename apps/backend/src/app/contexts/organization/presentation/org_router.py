"""조직 마스터 관리 API (부서·직위·직원). 권한: org.manage (전체 범위).

PATCH는 보낸 필드만 바꾼다. 부서의 parent_id에 null을 보내면 최상위 부서가 된다.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.org_service import (
    DepartmentChanges,
    OrganizationAdminService,
)
from app.contexts.organization.domain.entities import Department, Employee, EmployeePosition
from app.contexts.organization.domain.enums import EmploymentType
from app.contexts.organization.presentation.dependencies import (
    get_organization_admin_service,
    get_user_queries,
)
from app.contexts.organization.presentation.schemas import StaffUserSummary
from app.core.pagination import Page

router = APIRouter(prefix="/admin", tags=["admin-organization"])

Admin = Annotated[User, Depends(require_permission("org.manage"))]
ServiceDep = Annotated[OrganizationAdminService, Depends(get_organization_admin_service)]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]


# ---------------------------------------------------------------- 스키마
class DepartmentResponse(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    description: str
    rules: str | None

    @classmethod
    def of(cls, d: Department) -> "DepartmentResponse":
        return cls(
            id=d.id, parent_id=d.parent_id, name=d.name, description=d.description, rules=d.rules
        )


class DepartmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None
    rules: str | None = None


class DepartmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    parent_id: uuid.UUID | None = None
    rules: str | None = None


class PositionResponse(BaseModel):
    id: uuid.UUID
    name: str
    priority: int

    @classmethod
    def of(cls, p: EmployeePosition) -> "PositionResponse":
        return cls(id=p.id, name=p.name, priority=p.priority)


class PositionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    priority: int = Field(ge=0, le=32767)


class PositionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    priority: int | None = Field(default=None, ge=0, le=32767)


class EmployeeResponse(BaseModel):
    id: uuid.UUID
    user: StaffUserSummary | None
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType


class EmployeeUpdateRequest(BaseModel):
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    employment_type: EmploymentType | None = None


async def _employees(employees: list[Employee], users: UserQueries) -> list[EmployeeResponse]:
    found = await users.get_many([e.user_id for e in employees])
    responses = []
    for e in employees:
        user = found.get(e.user_id)
        responses.append(
            EmployeeResponse(
                id=e.id,
                user=StaffUserSummary(id=user.id, email=user.email, name=user.name)
                if user
                else None,
                department_id=e.department_id,
                position_id=e.position_id,
                employment_type=e.employment_type,
            )
        )
    return responses


# ---------------------------------------------------------------- 부서
@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(_: Admin, service: ServiceDep) -> list[DepartmentResponse]:
    """전체 부서 (평면 목록, parent_id로 트리를 만든다)."""
    return [DepartmentResponse.of(d) for d in await service.list_departments()]


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreateRequest, admin: Admin, service: ServiceDep
) -> DepartmentResponse:
    department = await service.create_department(
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
        rules=body.rules,
        actor_id=admin.id,
    )
    return DepartmentResponse.of(department)


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID, body: DepartmentUpdateRequest, admin: Admin, service: ServiceDep
) -> DepartmentResponse:
    sent = body.model_dump(exclude_unset=True)
    department = await service.update_department(
        department_id, DepartmentChanges(**sent), actor_id=admin.id
    )
    return DepartmentResponse.of(department)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: uuid.UUID, admin: Admin, service: ServiceDep
) -> Response:
    """하위 부서·직원·가입 신청이 참조 중이면 409 in_use."""
    await service.delete_department(department_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 직위
@router.get("/positions", response_model=list[PositionResponse])
async def list_positions(_: Admin, service: ServiceDep) -> list[PositionResponse]:
    """직위 목록 (우선순위가 높은 직급부터)."""
    return [PositionResponse.of(p) for p in await service.list_positions()]


@router.post("/positions", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    body: PositionCreateRequest, admin: Admin, service: ServiceDep
) -> PositionResponse:
    position = await service.create_position(
        name=body.name, priority=body.priority, actor_id=admin.id
    )
    return PositionResponse.of(position)


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID, body: PositionUpdateRequest, admin: Admin, service: ServiceDep
) -> PositionResponse:
    position = await service.update_position(
        position_id, name=body.name, priority=body.priority, actor_id=admin.id
    )
    return PositionResponse.of(position)


@router.delete("/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(position_id: uuid.UUID, admin: Admin, service: ServiceDep) -> Response:
    """직원·가입 신청이 쓰는 직위면 409 in_use."""
    await service.delete_position(position_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 직원
@router.get("/employees", response_model=Page[EmployeeResponse])
async def list_employees(
    _: Admin,
    service: ServiceDep,
    users: UsersDep,
    department_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EmployeeResponse]:
    """직원 목록 (담당자 배정 화면에서 직원을 고를 때도 쓴다)."""
    employees, total = await service.list_employees(
        department_id=department_id, limit=limit, offset=offset
    )
    return Page(items=await _employees(employees, users), total=total, limit=limit, offset=offset)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID, _: Admin, service: ServiceDep, users: UsersDep
) -> EmployeeResponse:
    return (await _employees([await service.get_employee(employee_id)], users))[0]


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    body: EmployeeUpdateRequest,
    admin: Admin,
    service: ServiceDep,
    users: UsersDep,
) -> EmployeeResponse:
    """부서·직위·고용 형태 이동. 직원 생성은 가입 승인으로만 한다."""
    employee = await service.update_employee(
        employee_id,
        department_id=body.department_id,
        position_id=body.position_id,
        employment_type=body.employment_type,
        actor_id=admin.id,
    )
    return (await _employees([employee], users))[0]

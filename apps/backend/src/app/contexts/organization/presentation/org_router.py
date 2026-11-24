"""조직 마스터 관리 API (부서·팀·과정 담당 팀·직위·직원). 권한: org.manage (전체 범위).

PATCH는 보낸 필드만 바꾼다. null을 보낼 수 있는 항목(팀 설명, 직위 담당 방식, 직원 팀)은
null을 보내면 값을 비운다 (A62).
"""

import uuid
from collections.abc import Iterable
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.application.permissions import PermissionTarget
from app.contexts.access.presentation.dependencies import (
    ApprovedUser,
    PermissionCheckerDep,
    require_permission,
)
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.org_service import (
    DepartmentChanges,
    EmployeeChanges,
    OrganizationAdminService,
    PositionChanges,
    TeamChanges,
)
from app.contexts.organization.domain.entities import (
    Department,
    Employee,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import AssignmentScope, EmploymentType, StaffRole
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
)
from app.contexts.organization.presentation.dependencies import (
    get_organization_admin_service,
    get_user_queries,
)
from app.contexts.organization.presentation.schemas import StaffUserSummary
from app.core.pagination import Page
from app.shared.errors import PermissionDeniedError

router = APIRouter(prefix="/admin", tags=["admin-organization"])

Admin = Annotated[User, Depends(require_permission("org.manage"))]
ServiceDep = Annotated[OrganizationAdminService, Depends(get_organization_admin_service)]
UsersDep = Annotated[UserQueries, Depends(get_user_queries)]


# ---------------------------------------------------------------- 스키마
class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    rules: str | None

    @classmethod
    def of(cls, d: Department) -> "DepartmentResponse":
        return cls(id=d.id, name=d.name, description=d.description, rules=d.rules)


class DepartmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=500)
    rules: str | None = None


class DepartmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    rules: str | None = None


class TeamResponse(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    description: str | None
    bootcamp_ids: list[uuid.UUID] = Field(description="담당 과정 (과정당 한 팀)")

    @classmethod
    def of(cls, t: Team, bootcamp_ids: list[uuid.UUID]) -> "TeamResponse":
        return cls(
            id=t.id,
            department_id=t.department_id,
            name=t.name,
            description=t.description,
            bootcamp_ids=bootcamp_ids,
        )


class TeamCreateRequest(BaseModel):
    department_id: uuid.UUID
    name: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=500)


class TeamUpdateRequest(BaseModel):
    department_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=500)


class BootcampTeamRequest(BaseModel):
    team_id: uuid.UUID | None = Field(description="담당 팀. null이면 담당 팀을 없앤다")


class BootcampTeamResponse(BaseModel):
    bootcamp_id: uuid.UUID
    team_id: uuid.UUID | None


class PositionResponse(BaseModel):
    id: uuid.UUID
    name: str
    priority: int
    assignment_scope: AssignmentScope | None

    @classmethod
    def of(cls, p: EmployeePosition) -> "PositionResponse":
        return cls(id=p.id, name=p.name, priority=p.priority, assignment_scope=p.assignment_scope)


class PositionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    priority: int = Field(ge=0, le=32767)
    assignment_scope: AssignmentScope | None = Field(
        default=None,
        description="COURSE: 팀의 과정 여러 개, COHORT: 팀 과정의 기수 하나, null: 담당 없음",
    )


class PositionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=20)
    priority: int | None = Field(default=None, ge=0, le=32767)
    assignment_scope: AssignmentScope | None = None


class EmployeeAssignmentResponse(BaseModel):
    staff_id: uuid.UUID = Field(description="담당자 행 (해제할 때 쓴다)")
    role: StaffRole
    bootcamp_id: uuid.UUID | None = Field(description="과정 담당이면 과정")
    cohort_id: uuid.UUID | None = Field(description="기수 담당이면 기수")
    bootcamp_name: str | None
    cohort_number: int | None


class EmployeeResponse(BaseModel):
    id: uuid.UUID
    user: StaffUserSummary | None
    department_id: uuid.UUID
    team_id: uuid.UUID | None
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[EmployeeAssignmentResponse] = Field(
        default_factory=list, description="담당 과정·기수 (A83)"
    )


class EmployeeUpdateRequest(BaseModel):
    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    employment_type: EmploymentType | None = None


def _sent(body: BaseModel, nullable: tuple[str, ...] = ()) -> dict[str, Any]:
    """보낸 항목만. null을 허용하지 않는 항목의 null은 보내지 않은 것으로 본다."""
    return {
        k: v
        for k, v in body.model_dump(exclude_unset=True).items()
        if v is not None or k in nullable
    }


class AcademyNames(Protocol):
    """academy `AcademyCatalog`: 담당 대상 이름 (A83)."""

    async def bootcamp_names(self, bootcamp_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]: ...
    async def cohort_labels(self, cohort_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Any]: ...


def get_academy_names(request: Request) -> AcademyNames:
    return cast("AcademyNames", request.app.state.academy_catalog)


AcademyDep = Annotated[AcademyNames, Depends(get_academy_names)]


async def _employees(
    employees: list[Employee], users: UserQueries, academy: AcademyNames
) -> list[EmployeeResponse]:
    ids = [e.id for e in employees]
    found = await users.get_many([e.user_id for e in employees])
    bootcamp_staffs = await TortoiseBootcampStaffRepository().list_by_employees(ids)
    cohort_staffs = await TortoiseCohortStaffRepository().list_by_employees(ids)
    names = await academy.bootcamp_names({s.bootcamp_id for s in bootcamp_staffs})
    labels = await academy.cohort_labels({s.cohort_id for s in cohort_staffs})
    assignments: dict[uuid.UUID, list[EmployeeAssignmentResponse]] = {i: [] for i in ids}
    for b in bootcamp_staffs:
        assignments[b.employee_id].append(
            EmployeeAssignmentResponse(
                staff_id=b.id,
                role=b.role,
                bootcamp_id=b.bootcamp_id,
                cohort_id=None,
                bootcamp_name=names.get(b.bootcamp_id),
                cohort_number=None,
            )
        )
    for c in cohort_staffs:
        label = labels.get(c.cohort_id)
        assignments[c.employee_id].append(
            EmployeeAssignmentResponse(
                staff_id=c.id,
                role=c.role,
                bootcamp_id=None,
                cohort_id=c.cohort_id,
                bootcamp_name=label.bootcamp_name if label else None,
                cohort_number=label.cohort_number if label else None,
            )
        )
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
                team_id=e.team_id,
                position_id=e.position_id,
                employment_type=e.employment_type,
                assignments=assignments.get(e.id, []),
            )
        )
    return responses


async def require_employee_viewer(user: ApprovedUser, checker: PermissionCheckerDep) -> User:
    """직원 조회: org.manage 또는 staff.assign(전체 범위) — 팀리드가 담당자를 고를 때 (A83)."""
    for code in ("org.manage", "staff.assign"):
        if await checker.has(user.id, code, PermissionTarget.global_()):
            return user
    raise PermissionDeniedError("이 작업을 할 권한이 없습니다.", code="permission_denied")


EmployeeViewer = Annotated[User, Depends(require_employee_viewer)]


# ---------------------------------------------------------------- 부서
@router.get("/departments", response_model=list[DepartmentResponse])
async def list_departments(_: Admin, service: ServiceDep) -> list[DepartmentResponse]:
    """전체 부서 (이름순)."""
    return [DepartmentResponse.of(d) for d in await service.list_departments()]


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreateRequest, admin: Admin, service: ServiceDep
) -> DepartmentResponse:
    department = await service.create_department(
        name=body.name,
        description=body.description,
        rules=body.rules,
        actor_id=admin.id,
    )
    return DepartmentResponse.of(department)


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID, body: DepartmentUpdateRequest, admin: Admin, service: ServiceDep
) -> DepartmentResponse:
    department = await service.update_department(
        department_id, DepartmentChanges(**_sent(body, ("rules",))), actor_id=admin.id
    )
    return DepartmentResponse.of(department)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: uuid.UUID, admin: Admin, service: ServiceDep
) -> Response:
    """팀·직원·가입 신청이 참조 중이면 409 in_use."""
    await service.delete_department(department_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 팀
@router.get("/teams", response_model=list[TeamResponse])
async def list_teams(_: Admin, service: ServiceDep) -> list[TeamResponse]:
    """전체 팀과 담당 과정 (이름순)."""
    return [TeamResponse.of(t, ids) for t, ids in await service.list_teams()]


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamCreateRequest, admin: Admin, service: ServiceDep) -> TeamResponse:
    team = await service.create_team(
        department_id=body.department_id,
        name=body.name,
        description=body.description,
        actor_id=admin.id,
    )
    return TeamResponse.of(team, [])


@router.patch("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID, body: TeamUpdateRequest, admin: Admin, service: ServiceDep
) -> TeamResponse:
    """부서를 바꾸면 팀이 다른 부서로 옮겨 간다 (담당 과정은 그대로)."""
    team = await service.update_team(
        team_id, TeamChanges(**_sent(body, ("description",))), actor_id=admin.id
    )
    ids = next((ids for t, ids in await service.list_teams() if t.id == team.id), [])
    return TeamResponse.of(team, ids)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    admin: Admin,
    service: ServiceDep,
    move_to_team_id: Annotated[
        uuid.UUID | None,
        Query(description="직원·가입 신청(이력 포함)·담당 과정을 옮길 팀"),
    ] = None,
) -> Response:
    """팀을 지운다. 참조가 있으면 `move_to_team_id`로 옮긴 뒤 지운다.

    옮길 팀 없이 참조가 남아 있으면 409 `team_in_use`, 같은 팀이면 422 `invalid_move_to_team`.
    """
    await service.delete_team(team_id, move_to_team_id=move_to_team_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/bootcamps/{bootcamp_id}/team", response_model=BootcampTeamResponse)
async def set_bootcamp_team(
    bootcamp_id: uuid.UUID, body: BootcampTeamRequest, admin: Admin, service: ServiceDep
) -> BootcampTeamResponse:
    """과정의 담당 팀을 정한다 (과정당 한 팀, A62)."""
    team_id = await service.set_bootcamp_team(bootcamp_id, body.team_id, actor_id=admin.id)
    return BootcampTeamResponse(bootcamp_id=bootcamp_id, team_id=team_id)


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
        name=body.name,
        priority=body.priority,
        assignment_scope=body.assignment_scope,
        actor_id=admin.id,
    )
    return PositionResponse.of(position)


@router.patch("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID, body: PositionUpdateRequest, admin: Admin, service: ServiceDep
) -> PositionResponse:
    position = await service.update_position(
        position_id, PositionChanges(**_sent(body, ("assignment_scope",))), actor_id=admin.id
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
    _: EmployeeViewer,
    service: ServiceDep,
    users: UsersDep,
    academy: AcademyDep,
    department_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=50, description="이름·이메일")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EmployeeResponse]:
    """직원 목록 (담당자 배정 화면에서 직원을 고를 때도 쓴다). 담당을 함께 준다 (A83)."""
    employees, total = await service.list_employees(
        department_id=department_id, team_id=team_id, query=q, limit=limit, offset=offset
    )
    return Page(
        items=await _employees(employees, users, academy), total=total, limit=limit, offset=offset
    )


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: uuid.UUID,
    _: EmployeeViewer,
    service: ServiceDep,
    users: UsersDep,
    academy: AcademyDep,
) -> EmployeeResponse:
    return (await _employees([await service.get_employee(employee_id)], users, academy))[0]


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID,
    body: EmployeeUpdateRequest,
    admin: Admin,
    service: ServiceDep,
    users: UsersDep,
    academy: AcademyDep,
) -> EmployeeResponse:
    """부서·팀·직위·고용 형태 이동 (존재만 검사). 직원 생성은 가입 승인으로만 한다."""
    employee = await service.update_employee(
        employee_id, EmployeeChanges(**_sent(body, ("team_id",))), actor_id=admin.id
    )
    return (await _employees([employee], users, academy))[0]

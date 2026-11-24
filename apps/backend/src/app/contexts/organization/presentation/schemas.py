"""organization 요청·응답 스키마."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.identity.domain.enums import UserApprovalStatus
from app.contexts.organization.domain.enums import (
    AssignmentScope,
    EmployeeRegistrationStatus,
    EmploymentType,
)
from app.contexts.organization.domain.registration import MAX_ASSIGNMENTS, REJECT_REASON_MAX_LENGTH


class DepartmentOption(BaseModel):
    id: uuid.UUID
    name: str


class TeamOption(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str


class PositionOption(BaseModel):
    id: uuid.UUID
    name: str
    assignment_scope: AssignmentScope | None = Field(
        description="담당 방식. COURSE: 팀의 과정 여러 개(운영 매니저), "
        "COHORT: 팀 과정의 기수 하나(조교), null: 담당 없음 (A62)"
    )


class BootcampOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    team_id: uuid.UUID | None = Field(description="담당 팀 (A62)")


class CohortOption(BaseModel):
    id: uuid.UUID
    bootcamp_id: uuid.UUID
    cohort_number: int
    status: CohortStatus
    start_date: date
    end_date: date


class StaffRegistrationOptionsResponse(BaseModel):
    departments: list[DepartmentOption]
    teams: list[TeamOption]
    positions: list[PositionOption]
    employment_types: list[EmploymentType]
    bootcamps: list[BootcampOption]
    cohorts: list[CohortOption] = Field(
        description="기수 담당으로 고를 수 있는 기수: 진행 예정·진행 중 기수 중 "
        "기수 담당자가 없는 기수 (A63·A89)"
    )


class AssignmentPayload(BaseModel):
    """담당 1건: 과정 또는 기수 (담당 방식은 직위가 정한다, A89)."""

    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None


class StaffRegistrationRequest(BaseModel):
    department_id: uuid.UUID
    team_id: uuid.UUID | None = None
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[AssignmentPayload] = Field(default_factory=list, max_length=MAX_ASSIGNMENTS)


class StaffRegistrationResponse(BaseModel):
    id: uuid.UUID
    status: EmployeeRegistrationStatus
    department_id: uuid.UUID
    team_id: uuid.UUID | None
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[AssignmentPayload]
    reviewed_at: datetime | None
    reject_reason: str | None
    created_at: datetime | None


class ApplicantSummary(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    approval_status: UserApprovalStatus


class AdminStaffRegistrationResponse(StaffRegistrationResponse):
    applicant: ApplicantSummary | None


class ApproveStaffRegistrationRequest(BaseModel):
    """승인할 때 조정할 항목. 보내지 않은(null) 항목은 신청한 값을 그대로 쓴다.

    assignments를 보내면 담당 목록 전체를 그 값으로 바꾼다(빈 배열이면 담당 없음).
    team_id는 보내지 않으면 신청값, null을 보내면 팀 없음(부서 직속)이다.
    조정은 자유이고 존재만 검사한다 (A62).
    """

    department_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    employment_type: EmploymentType | None = None
    assignments: list[AssignmentPayload] | None = Field(default=None, max_length=MAX_ASSIGNMENTS)


class RejectStaffRegistrationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=REJECT_REASON_MAX_LENGTH)


class StaffUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    name: str


class StaffMemberResponse(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    user: StaffUserSummary | None
    created_at: datetime | None


class AssignStaffRequest(BaseModel):
    employee_id: uuid.UUID

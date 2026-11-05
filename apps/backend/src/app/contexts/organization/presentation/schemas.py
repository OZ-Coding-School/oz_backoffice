"""organization 요청·응답 스키마."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.organization.domain.enums import (
    EmployeeRegistrationStatus,
    EmploymentType,
    StaffRole,
)
from app.contexts.organization.domain.registration import MAX_ASSIGNMENTS


class DepartmentOption(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str


class PositionOption(BaseModel):
    id: uuid.UUID
    name: str


class BootcampOption(BaseModel):
    id: uuid.UUID
    name: str
    code: str


class CohortOption(BaseModel):
    id: uuid.UUID
    bootcamp_id: uuid.UUID
    cohort_number: int
    status: CohortStatus
    start_date: date
    end_date: date


class StaffRegistrationOptionsResponse(BaseModel):
    departments: list[DepartmentOption]
    positions: list[PositionOption]
    employment_types: list[EmploymentType]
    staff_roles: list[StaffRole]
    bootcamps: list[BootcampOption]
    cohorts: list[CohortOption]


class AssignmentPayload(BaseModel):
    role: StaffRole
    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None


class StaffRegistrationRequest(BaseModel):
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[AssignmentPayload] = Field(default_factory=list, max_length=MAX_ASSIGNMENTS)


class StaffRegistrationResponse(BaseModel):
    id: uuid.UUID
    status: EmployeeRegistrationStatus
    department_id: uuid.UUID
    position_id: uuid.UUID
    employment_type: EmploymentType
    assignments: list[AssignmentPayload]
    reviewed_at: datetime | None
    reject_reason: str | None
    created_at: datetime | None

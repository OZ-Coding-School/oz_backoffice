"""내 수강 등록 목록 API (decisions A64).

GET /me/enrollments — 승인된 회원. 내 계정에 연결된 수강 등록을 상태와 무관하게 모두 보낸다.
수강 등록이 없으면(멘토 등) 빈 목록이다. 회원 한 명의 등록은 몇 건이라 페이지를 나누지 않는다.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.contexts.academy.application.enrollment_queries import EnrollmentQueries, MyEnrollment
from app.contexts.academy.domain.enums import CohortStatus, EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.access.presentation.dependencies import ApprovedUser

router = APIRouter(prefix="/me/enrollments", tags=["my-enrollments"])


def get_enrollment_queries() -> EnrollmentQueries:
    return EnrollmentQueries(
        students=TortoiseStudentRepository(),
        cohorts=TortoiseCohortRepository(),
        bootcamps=TortoiseBootcampRepository(),
    )


QueriesDep = Annotated[EnrollmentQueries, Depends(get_enrollment_queries)]


class EnrollmentResponse(BaseModel):
    student_id: uuid.UUID = Field(description="수강 등록 id")
    cohort_id: uuid.UUID
    bootcamp_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int
    cohort_status: CohortStatus
    start_date: date = Field(description="기수 시작일")
    end_date: date = Field(description="기수 종료일")
    status: EnrollmentStatus = Field(description="수강 상태")
    enrolled_at: date
    ended_at: date | None = Field(description="수강 종료일 (수강 중이면 null)")

    @classmethod
    def of(cls, e: MyEnrollment) -> "EnrollmentResponse":
        return cls(
            student_id=e.student.id,
            cohort_id=e.cohort.id,
            bootcamp_id=e.bootcamp.id,
            bootcamp_name=e.bootcamp.name,
            cohort_number=e.cohort.cohort_number,
            cohort_status=e.cohort.status,
            start_date=e.cohort.start_date,
            end_date=e.cohort.end_date,
            status=e.student.status,
            enrolled_at=e.student.enrolled_at,
            ended_at=e.student.ended_at,
        )


@router.get("", response_model=list[EnrollmentResponse])
async def my_enrollments(user: ApprovedUser, queries: QueriesDep) -> list[EnrollmentResponse]:
    """내 수강 등록 (기수 시작일이 늦은 것부터)."""
    return [EnrollmentResponse.of(e) for e in await queries.of_user(user.id)]

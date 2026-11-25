"""기수 요약 (decisions A96): 수강생 인원·배정 멘토·담당자.

멘토(멘토링)·담당자(조직)는 다른 컨텍스트라 `app/composition`의 조합 서비스가 채우고,
라우터는 `app.state.cohort_summary`로 받는다(B10).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class CohortStudentCounts:
    total: int = 0
    linked: int = 0  # 가입해 회원과 연결된 수강생
    by_status: dict[str, int] = field(default_factory=dict)  # EnrollmentStatus 값별


@dataclass(frozen=True, slots=True)
class CohortSummaryMentor:
    mentor_id: uuid.UUID
    name: str
    start_date: date


@dataclass(frozen=True, slots=True)
class CohortSummaryStaff:
    employee_id: uuid.UUID
    name: str
    position_name: str | None
    scope: Literal["COHORT", "COURSE"]


@dataclass(frozen=True, slots=True)
class CohortSummary:
    students: CohortStudentCounts
    mentors: list[CohortSummaryMentor]
    staff: list[CohortSummaryStaff]


class CohortSummaryReader(Protocol):
    async def summary_of(self, cohort_id: uuid.UUID, bootcamp_id: uuid.UUID) -> CohortSummary: ...

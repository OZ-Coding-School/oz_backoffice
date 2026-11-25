"""수강생 상세 (decisions A99): 기본·수강 정보 + 가입 계정 + 멘토링 요약.

회원(identity)·멘토링은 다른 컨텍스트라 `app/composition`의 조합 서비스가 채우고,
라우터는 `app.state.student_detail`로 받는다(B10).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.contexts.academy.domain.entities import Student


@dataclass(frozen=True, slots=True)
class StudentMember:
    user_id: uuid.UUID
    email: str
    approved_at: datetime | None


@dataclass(frozen=True, slots=True)
class StudentAccount:
    id: uuid.UUID
    valid_from: date
    valid_until: date
    is_expired: bool
    total_minutes: int
    held_minutes: int
    used_minutes: int
    remaining_minutes: int


@dataclass(frozen=True, slots=True)
class StudentMentoring:
    team_id: uuid.UUID | None
    team_label: str | None
    account: StudentAccount | None
    pending_requests: int
    upcoming_sessions: int
    completed_sessions: int


@dataclass(frozen=True, slots=True)
class StudentDetail:
    student: Student
    member: StudentMember | None
    mentoring: StudentMentoring


class StudentDetailReader(Protocol):
    async def detail_of(
        self, cohort_id: uuid.UUID, student_id: uuid.UUID, *, today: date
    ) -> StudentDetail:
        """그 기수의 수강생이 아니면 NotFoundError(`student_not_found`)."""
        ...

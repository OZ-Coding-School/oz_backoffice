"""수강 등록 조회 (다른 컨텍스트용 공개 서비스).

멘토링(신청 가능 시간 조회 권한 A37, 팀 구성·시간 지급 A39)이 쓴다.
"수강 중"은 수강 상태가 ENROLLED이고 Airtable 원천에서 삭제되지 않은 등록이다.
"""

import uuid

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.repositories import StudentRepository


def is_active_enrollment(student: Student) -> bool:
    return student.is_enrolled and not student.is_removed_in_source


class StudentQueries:
    def __init__(self, students: StudentRepository) -> None:
        self._students = students

    async def is_enrolled(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> bool:
        """그 기수 명단에 본인 계정이 연결돼 있고 수강 중인지."""
        student = await self._students.get_by_user_and_cohort(user_id, cohort_id)
        return student is not None and is_active_enrollment(student)

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {s.id: s for s in await self._students.list_by_ids(student_ids)}

    async def enrolled_in_cohort(self, cohort_id: uuid.UUID) -> list[Student]:
        """그 기수의 수강 중 수강생 (가입 여부 무관, 이름순)."""
        students = await self._students.list_by_cohort(
            cohort_id, claimed=None, include_removed=False
        )
        return [s for s in students if is_active_enrollment(s)]

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        """회원의 모든 수강 등록 (상태 무관)."""
        return await self._students.list_by_user(user_id)

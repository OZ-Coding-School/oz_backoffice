"""수강 등록 조회 (다른 컨텍스트용 공개 서비스).

멘토링(신청 가능 시간 조회 권한, decisions A37)이 쓴다.
"""

import uuid

from app.contexts.academy.domain.repositories import StudentRepository


class StudentQueries:
    def __init__(self, students: StudentRepository) -> None:
        self._students = students

    async def is_enrolled(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> bool:
        """그 기수 명단에 본인 계정이 연결돼 있고 수강 중(ENROLLED)인지."""
        student = await self._students.get_by_user_and_cohort(user_id, cohort_id)
        return student is not None and student.is_enrolled

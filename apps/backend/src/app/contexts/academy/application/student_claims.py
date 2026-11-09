"""가입한 수강생을 명단(수강 등록)에 연결한다 (decisions A6·A10·A31).

다른 컨텍스트(가입)용 공개 서비스다.

신청한 기수 안에서만 찾는다: 이름 + 휴대폰이 같고, 수강 중이며, 원천에 있고, 아직 회원과
연결되지 않은 명단. 정확히 1건이면 연결한다. 0건·2건 이상은 연결하지 않는다(승인 대기).
트랜잭션은 호출하는 쪽(가입 서비스)이 연다.
"""

import uuid
from dataclasses import dataclass

from app.contexts.academy.domain.repositories import StudentRepository


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    candidate_count: int  # 신청 기수 안의 후보 수
    student_id: uuid.UUID | None  # 연결한 수강 등록 (1건일 때만)


class StudentClaims:
    def __init__(self, students: StudentRepository) -> None:
        self._students = students

    async def claim_in_cohort(
        self, cohort_id: uuid.UUID, *, name: str, phone_number: str, user_id: uuid.UUID
    ) -> ClaimOutcome:
        candidates = [
            s
            for s in await self._students.find_claimable_by_name_and_phone(name, phone_number)
            if s.cohort_id == cohort_id
        ]
        if len(candidates) != 1:
            return ClaimOutcome(candidate_count=len(candidates), student_id=None)
        student = candidates[0]
        student.claim(user_id)
        await self._students.save(student)
        return ClaimOutcome(candidate_count=1, student_id=student.id)

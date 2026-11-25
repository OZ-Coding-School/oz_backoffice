"""수강생 상세 조합 (decisions A99).

수강 정보는 학사 명단, 가입 계정은 회원, 멘토링 요약은 멘티 목록(A59)과 같은 기준으로 모은다.
"""

import uuid
from datetime import date

from app.contexts.academy.application.student_detail import (
    StudentAccount,
    StudentDetail,
    StudentMember,
    StudentMentoring,
)
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.mentoring.application.mentee_queries import CohortRoster, MenteeQueries
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.shared.errors import NotFoundError


class StudentDetailComposer:
    def __init__(self, roster: CohortRoster) -> None:
        self._mentees = MenteeQueries(
            roster=roster,
            teams=TortoiseMentoringTeamRepository(),
            accounts=TortoiseBalanceAccountRepository(),
            requests=TortoiseMentoringRequestRepository(),
            sessions=TortoiseMentoringSessionRepository(),
        )

    async def detail_of(
        self, cohort_id: uuid.UUID, student_id: uuid.UUID, *, today: date
    ) -> StudentDetail:
        student = await TortoiseStudentRepository().get(student_id)
        if student is None or student.cohort_id != cohort_id:
            raise NotFoundError("수강생을 찾을 수 없습니다.", code="student_not_found")
        user = await TortoiseUserRepository().get(student.user_id) if student.user_id else None
        summary = await self._mentees.of_student(student)
        a = summary.account
        return StudentDetail(
            student=student,
            member=StudentMember(user_id=user.id, email=user.email, approved_at=user.approved_at)
            if user
            else None,
            mentoring=StudentMentoring(
                team_id=summary.team.id if summary.team else None,
                team_label=summary.team.label if summary.team else None,
                account=StudentAccount(
                    id=a.id,
                    valid_from=a.valid_from,
                    valid_until=a.valid_until,
                    is_expired=a.is_expired(today),
                    total_minutes=a.total_minutes,
                    held_minutes=a.held_minutes,
                    used_minutes=a.used_minutes,
                    remaining_minutes=a.remaining_minutes,
                )
                if a
                else None,
                pending_requests=summary.pending_requests,
                upcoming_sessions=summary.upcoming_sessions,
                completed_sessions=summary.completed_sessions,
            ),
        )

"""멘토링 세션 조회 (decisions A42·A43).

- 수강생: 본인 1:1 세션과 소속 팀 세션(팀원 모두 조회).
- 멘토: 본인 세션.
- 운영진: 기수 범위(`mentoring.request.read`)의 세션. 권한은 라우터가 검사한다.
- 단건 조회는 참여자(1:1 신청 수강생·팀원)와 멘토 본인만, 아니면 404로 숨긴다.
기록·메모·Meet은 P12·P13.
"""

import uuid
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.repositories import (
    MentoringRequestRepository,
    MentoringSessionRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.session import MentoringSession, SessionQuery
from app.shared.errors import NotFoundError


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...
    async def of_user(self, user_id: uuid.UUID) -> list[Student]: ...


class MentorLookup(Protocol):
    """educator `MentorQueries`."""

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


def _not_found() -> NotFoundError:
    return NotFoundError("세션을 찾을 수 없습니다.", code="session_not_found")


class MentoringSessionQueries:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        requests: MentoringRequestRepository,
        teams: MentoringTeamRepository,
        students: StudentLookup,
        mentors: MentorLookup,
    ) -> None:
        self._sessions = sessions
        self._requests = requests
        self._teams = teams
        self._students = students
        self._mentors = mentors

    async def list_mine(
        self, user_id: uuid.UUID, query: SessionQuery
    ) -> tuple[list[MentoringSession], int]:
        student_ids, team_ids = await self._memberships(user_id)
        return await self._sessions.list_for_participants(
            student_ids=student_ids, team_ids=team_ids, query=query
        )

    async def list_for_mentor(
        self, user_id: uuid.UUID, query: SessionQuery
    ) -> tuple[list[MentoringSession], int]:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        return await self._sessions.list_for_mentor(mentor.id, query)

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID | None,
        query: SessionQuery,
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[MentoringSession], int]:
        return await self._sessions.list_by_cohort(
            cohort_id, mentor_id=mentor_id, query=query, student_id=student_id, team_id=team_id
        )

    async def get_for_user(self, user_id: uuid.UUID, session_id: uuid.UUID) -> MentoringSession:
        session = await self._sessions.get(session_id)
        if session is None:
            raise _not_found()
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is not None and mentor.id == session.mentor_id:
            return session
        request = await self._requests.get(session.request_id)
        student_ids, team_ids = await self._memberships(user_id)
        if request is not None and (
            (request.team_id is not None and request.team_id in team_ids)
            or (request.team_id is None and request.requester_id in student_ids)
        ):
            return session
        raise _not_found()

    async def get_for_cohort(self, cohort_id: uuid.UUID, session_id: uuid.UUID) -> MentoringSession:
        session = await self._sessions.get(session_id)
        if session is None:
            raise _not_found()
        request = await self._requests.get(session.request_id)
        requester = (
            (await self._students.get_many([request.requester_id])).get(request.requester_id)
            if request
            else None
        )
        if requester is None or requester.cohort_id != cohort_id:
            raise _not_found()
        return session

    async def _memberships(self, user_id: uuid.UUID) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        registrations = await self._students.of_user(user_id)
        student_ids = [s.id for s in registrations]
        teams = await self._teams.list_by_students(student_ids)
        return student_ids, [t.id for t in teams]

"""수강생 멘토링 신청 준비 조회 (decisions A64, BE-1).

- 기수 멘토링 설정 요약: 신청 화면에 필요한 값(허용 종류·진행 단위·신청 마감·대기 신청 한도)만
- 신청 받는 멘토 목록: 그 기수에 활성 배정된 활성 멘토 중 신청 받기를 켠 멘토 (F13)
- 멘토 한 명: 그 기수에 활성 배정된 멘토면 신청을 받지 않아도 보인다 (팀 멘토 확인·소개 모달)
모두 그 기수의 수강 중 수강생만 볼 수 있다 (신청 가능 시간 API와 같음).
"""

import uuid
from typing import Protocol

from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.application.availability_service import EnrollmentLookup
from app.contexts.mentoring.domain.repositories import (
    CohortMentoringSettingsRepository,
    CohortMentorRepository,
)
from app.contexts.mentoring.domain.settings import CohortMentoringSettings
from app.shared.errors import NotFoundError, PermissionDeniedError


class MentorProfiles(Protocol):
    """educator `MentorQueries`."""

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]: ...


class StudentMentoringQueries:
    def __init__(
        self,
        *,
        settings: CohortMentoringSettingsRepository,
        assignments: CohortMentorRepository,
        mentors: MentorProfiles,
        enrollments: EnrollmentLookup,
    ) -> None:
        self._settings = settings
        self._assignments = assignments
        self._mentors = mentors
        self._enrollments = enrollments

    async def settings(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> CohortMentoringSettings:
        await self._ensure_enrolled(user_id, cohort_id)
        settings = await self._settings.get_by_cohort(cohort_id)
        if settings is None:
            raise NotFoundError(
                "이 기수의 멘토링 설정이 아직 없습니다.", code="mentoring_settings_not_configured"
            )
        return settings

    async def accepting_mentors(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> list[Mentor]:
        """신청 받는 멘토 (순서는 표시 이름을 아는 쪽에서 정한다)."""
        await self._ensure_enrolled(user_id, cohort_id)
        assigned = await self._assignments.list_by_cohort(cohort_id, include_inactive=False)
        mentors = await self._mentors.get_many(list({a.mentor_id for a in assigned}))
        return [m for m in mentors.values() if m.is_active and m.accepting_requests]

    async def mentor(
        self, user_id: uuid.UUID, cohort_id: uuid.UUID, mentor_id: uuid.UUID
    ) -> Mentor:
        await self._ensure_enrolled(user_id, cohort_id)
        mentor = await self._mentors.get(mentor_id)
        assigned = await self._assignments.find_active(mentor_id, cohort_id)
        if mentor is None or assigned is None or not mentor.is_active:
            raise NotFoundError("이 기수에 배정된 멘토가 아닙니다.", code="mentor_not_assigned")
        return mentor

    async def _ensure_enrolled(self, user_id: uuid.UUID, cohort_id: uuid.UUID) -> None:
        if not await self._enrollments.is_enrolled(user_id, cohort_id):
            raise PermissionDeniedError(
                "이 기수의 수강 중 수강생만 볼 수 있습니다.", code="not_enrolled_in_cohort"
            )

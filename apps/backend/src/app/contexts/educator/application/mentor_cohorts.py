"""멘토의 활성 배정 기수 (decisions A100).

배정(멘토링)·기수 이름(학사)은 다른 컨텍스트라 `app/composition`이 채우고,
라우터는 `app.state.mentor_cohorts`로 받는다(B10).
"""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MentorCohort:
    cohort_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int


class MentorCohortReader(Protocol):
    async def active_cohorts(
        self, mentor_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[MentorCohort]]:
        """멘토별 활성 배정 기수 (최근 배정부터)."""
        ...

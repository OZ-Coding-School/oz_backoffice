"""멘토별 활성 배정 기수 조합 (decisions A100)."""

import uuid

from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.educator.application.mentor_cohorts import MentorCohort
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository


class MentorCohortComposer:
    async def active_cohorts(
        self, mentor_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[MentorCohort]]:
        assignments = await TortoiseCohortMentorRepository().list_active_by_mentors(mentor_ids)
        if not assignments:
            return {}
        cohorts = {
            c.id: c
            for c in await TortoiseCohortRepository().list_by_ids(
                {a.cohort_id for a in assignments}
            )
        }
        bootcamps = {b.id: b.name for b in await TortoiseBootcampRepository().list_all()}
        out: dict[uuid.UUID, list[MentorCohort]] = {}
        for a in assignments:
            cohort = cohorts.get(a.cohort_id)
            if cohort is None:
                continue
            out.setdefault(a.mentor_id, []).append(
                MentorCohort(
                    cohort_id=cohort.id,
                    bootcamp_name=bootcamps.get(cohort.bootcamp_id, "—"),
                    cohort_number=cohort.cohort_number,
                )
            )
        return out

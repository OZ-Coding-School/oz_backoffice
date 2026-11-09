"""명단 동기화 조회 (실행 이력, 기수 명단, 실패 목록)."""

import uuid

from app.contexts.academy.domain.entities import RosterSyncRun, Student
from app.contexts.academy.domain.enums import RosterSyncScope
from app.contexts.academy.domain.repositories import (
    CohortRepository,
    RosterSyncRunRepository,
    StudentRepository,
)
from app.shared.errors import NotFoundError


class RosterQueries:
    def __init__(
        self,
        *,
        runs: RosterSyncRunRepository,
        students: StudentRepository,
        cohorts: CohortRepository,
    ) -> None:
        self._runs = runs
        self._students = students
        self._cohorts = cohorts

    async def recent_runs(self, *, before: uuid.UUID | None, limit: int) -> list[RosterSyncRun]:
        return await self._runs.list_recent(before=before, limit=limit)

    async def get_run(self, run_id: uuid.UUID) -> RosterSyncRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError("동기화 실행을 찾을 수 없습니다.", code="roster_sync_run_not_found")
        return run

    async def latest_unmapped(self) -> RosterSyncRun | None:
        """가장 최근에 성공한 전체 동기화 (실패 목록은 실행 범위에 따라 다르므로 전체 기준)."""
        return await self._runs.latest_succeeded(RosterSyncScope.ALL)

    async def cohort_students(
        self, cohort_id: uuid.UUID, *, claimed: bool | None, include_removed: bool
    ) -> list[Student]:
        if await self._cohorts.get(cohort_id) is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")
        return await self._students.list_by_cohort(
            cohort_id, claimed=claimed, include_removed=include_removed
        )

"""과정·기수 선택지 조회 (다른 컨텍스트가 쓰는 공개 서비스).

운영진 가입 신청(organization)에서 담당 과정·기수를 고를 때, 권한 판정(access)에서
기수가 속한 과정을 찾을 때 쓴다.
담당으로 고를 수 있는 것은 활성 과정과, 준비·진행 중인 기수다.
"""

import uuid
from collections.abc import Iterable

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.domain.repositories import BootcampRepository, CohortRepository
from app.shared.errors import BusinessRuleViolation

STAFFABLE_COHORT_STATUSES = (CohortStatus.PLANNED, CohortStatus.ONGOING)


class AcademyCatalog:
    def __init__(self, bootcamps: BootcampRepository, cohorts: CohortRepository) -> None:
        self._bootcamps = bootcamps
        self._cohorts = cohorts

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None:
        """기수가 속한 과정 (권한 범위 판정용). 없는 기수면 None."""
        cohort = await self._cohorts.get(cohort_id)
        return cohort.bootcamp_id if cohort else None

    async def staffable_bootcamps(self) -> list[Bootcamp]:
        return await self._bootcamps.list_active()

    async def staffable_cohorts(self) -> list[Cohort]:
        active = {bootcamp.id for bootcamp in await self._bootcamps.list_active()}
        cohorts = await self._cohorts.list_by_statuses(STAFFABLE_COHORT_STATUSES)
        return [cohort for cohort in cohorts if cohort.bootcamp_id in active]

    async def ensure_staffable(
        self, *, bootcamp_ids: Iterable[uuid.UUID], cohort_ids: Iterable[uuid.UUID]
    ) -> None:
        """담당으로 고를 수 없는(없거나 비활성·종료된) 과정·기수가 있으면 거부한다."""
        wanted_bootcamps, wanted_cohorts = set(bootcamp_ids), set(cohort_ids)
        if wanted_bootcamps:
            allowed = {bootcamp.id for bootcamp in await self.staffable_bootcamps()}
            if not wanted_bootcamps <= allowed:
                raise BusinessRuleViolation(
                    "담당으로 선택할 수 없는 과정이 있습니다.", code="invalid_staff_target"
                )
        if wanted_cohorts:
            allowed = {cohort.id for cohort in await self.staffable_cohorts()}
            if not wanted_cohorts <= allowed:
                raise BusinessRuleViolation(
                    "담당으로 선택할 수 없는 기수가 있습니다.", code="invalid_staff_target"
                )

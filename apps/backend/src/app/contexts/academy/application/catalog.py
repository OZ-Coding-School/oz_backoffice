"""과정·기수 선택지 조회 (다른 컨텍스트가 쓰는 공개 서비스).

운영진 가입 신청(organization)에서 담당 과정·기수를 고를 때, 권한 판정(access)에서
기수가 속한 과정을 찾을 때, 수강생 가입(identity)에서 기수를 고를 때 쓴다.
담당으로 고를 수 있는 것은 활성 과정과, 준비·진행 중인 기수다.
"""

import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.domain.repositories import BootcampRepository, CohortRepository
from app.shared.errors import BusinessRuleViolation

STAFFABLE_COHORT_STATUSES = (CohortStatus.PLANNED, CohortStatus.ONGOING)


@dataclass(frozen=True, slots=True)
class CohortLabel:
    """화면 표시용 기수 이름 (과정명 + 기수 번호)."""

    cohort_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int


@dataclass(frozen=True, slots=True)
class CohortSummary:
    """운영진 '현재 기수' 선택지 (A81)."""

    id: uuid.UUID
    bootcamp_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int
    start_date: date
    end_date: date
    status: CohortStatus


# 진행 중 → 예정 → 종료 → 비활성. 보관(ARCHIVED)은 목록에서 숨긴다
_SCOPE_ORDER = {
    CohortStatus.ONGOING: 0,
    CohortStatus.PLANNED: 1,
    CohortStatus.ENDED: 2,
    CohortStatus.INACTIVE: 3,
}


class AcademyCatalog:
    def __init__(self, bootcamps: BootcampRepository, cohorts: CohortRepository) -> None:
        self._bootcamps = bootcamps
        self._cohorts = cohorts

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None:
        """기수가 속한 과정 (권한 범위 판정용). 없는 기수면 None."""
        cohort = await self._cohorts.get(cohort_id)
        return cohort.bootcamp_id if cohort else None

    async def get_bootcamp(self, bootcamp_id: uuid.UUID) -> Bootcamp | None:
        return await self._bootcamps.get(bootcamp_id)

    async def get_cohort(self, cohort_id: uuid.UUID) -> Cohort | None:
        return await self._cohorts.get(cohort_id)

    async def cohort_labels(self, cohort_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, CohortLabel]:
        cohorts = await self._cohorts.list_by_ids(set(cohort_ids))
        if not cohorts:
            return {}
        names = {bootcamp.id: bootcamp.name for bootcamp in await self._bootcamps.list_all()}
        return {
            c.id: CohortLabel(c.id, names.get(c.bootcamp_id, ""), c.cohort_number) for c in cohorts
        }

    async def cohorts_in_scope(
        self,
        *,
        all_cohorts: bool,
        bootcamp_ids: Collection[uuid.UUID] = (),
        cohort_ids: Collection[uuid.UUID] = (),
    ) -> list[CohortSummary]:
        """권한 범위 안의 기수 (A81): 전체이거나, 그 과정의 기수와 그 기수. 보관은 뺀다.
        진행 중 → 예정 → 종료 → 비활성, 같은 상태 안에서는 최근 시작 순."""
        if not (all_cohorts or bootcamp_ids or cohort_ids):
            return []
        cohorts = await self._cohorts.list_by_statuses(tuple(_SCOPE_ORDER))
        if not all_cohorts:
            cohorts = [c for c in cohorts if c.bootcamp_id in bootcamp_ids or c.id in cohort_ids]
        names = {bootcamp.id: bootcamp.name for bootcamp in await self._bootcamps.list_all()}
        cohorts.sort(
            key=lambda c: (_SCOPE_ORDER[c.status], -c.start_date.toordinal(), -c.cohort_number)
        )
        return [
            CohortSummary(
                id=c.id,
                bootcamp_id=c.bootcamp_id,
                bootcamp_name=names.get(c.bootcamp_id, ""),
                cohort_number=c.cohort_number,
                start_date=c.start_date,
                end_date=c.end_date,
                status=c.status,
            )
            for c in cohorts
        ]

    async def staffable_bootcamps(self) -> list[Bootcamp]:
        return await self._bootcamps.list_active()

    async def staffable_cohorts(self) -> list[Cohort]:
        active = {bootcamp.id for bootcamp in await self._bootcamps.list_active()}
        cohorts = await self._cohorts.list_by_statuses(STAFFABLE_COHORT_STATUSES)
        return [cohort for cohort in cohorts if cohort.bootcamp_id in active]

    async def is_signup_cohort(self, cohort_id: uuid.UUID) -> bool:
        """수강생 가입 때 고를 수 있는 기수인지 (활성 과정의 PLANNED·ONGOING, decisions A30)."""
        return any(cohort.id == cohort_id for cohort in await self.staffable_cohorts())

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

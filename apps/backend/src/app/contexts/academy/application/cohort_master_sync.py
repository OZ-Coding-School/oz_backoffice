"""Airtable 과정-기수 테이블 → 학사 마스터 동기화 (decisions A20, D6 보완).

레코드(기수)마다:
1. HRD 과정: 훈련과정ID로 찾고 없으면 만든다. 과정명이 바뀌면 고친다.
2. HRD 회차: (HRD 과정, 훈련회차)로 찾고 없으면 만든다. 훈련 기간을 맞춘다.
3. 운영과정: 과정코드로 찾고 없으면 만든다(이름 = 기수 별칭, 대표 HRD 과정 = 그 코드의 기수가
   가장 많이 속한 HRD 과정). Airtable 기수 별칭을 맞춘다.
4. 기수: Airtable 레코드 ID → (운영과정, 기수 번호) 순으로 찾고 없으면 만든다.
   HRD 회차·기간·진행상태를 맞추되, 운영진이 정한 INACTIVE·ARCHIVED는 덮어쓰지 않는다.
필수 값이 없거나 규칙에 어긋나는 레코드는 실패 목록에 남기고 건너뛴다.
"""

import dataclasses
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.contexts.academy.domain.cohort_source import (
    MANUAL_COHORT_STATUSES,
    CohortFieldMap,
    CohortSource,
    interpret_cohort,
)
from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
)
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.domain.repositories import (
    BootcampRepository,
    CohortRepository,
    HrdNetBootcampCohortRepository,
    HrdNetBootcampRepository,
)
from app.contexts.academy.domain.roster import UnmappedRecord
from app.shared.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


@dataclass
class MasterSyncResult:
    fetched: int = 0
    created_bootcamps: int = 0
    created_cohorts: int = 0
    updated_cohorts: int = 0
    unmapped: list[UnmappedRecord] = field(default_factory=list)


class CohortMasterSync:
    def __init__(
        self,
        *,
        field_map: CohortFieldMap,
        hrd_bootcamps: HrdNetBootcampRepository,
        hrd_cohorts: HrdNetBootcampCohortRepository,
        bootcamps: BootcampRepository,
        cohorts: CohortRepository,
    ) -> None:
        self._fields = field_map
        self._hrd_bootcamps = hrd_bootcamps
        self._hrd_cohorts = hrd_cohorts
        self._bootcamps = bootcamps
        self._cohorts = cohorts

    async def apply(self, fetched: list[tuple[str, dict[str, Any]]]) -> MasterSyncResult:
        """호출하는 쪽이 UnitOfWork를 연다."""
        result = MasterSyncResult(fetched=len(fetched))
        sources: list[CohortSource] = []
        for record_id, values in fetched:
            interpreted = interpret_cohort(record_id, values, self._fields)
            if isinstance(interpreted, UnmappedRecord):
                result.unmapped.append(interpreted)
            elif interpreted is not None:
                sources.append(interpreted)

        hrd_by_id: dict[str, HrdNetBootcamp] = {}
        for source in sources:
            hrd_by_id[source.hrd_net_id] = await self._hrd_bootcamp(source, hrd_by_id)
        representative = _representative_hrd(sources)
        bootcamp_by_code: dict[str, Bootcamp] = {}
        for source in sources:
            try:
                if source.code not in bootcamp_by_code:
                    hrd = hrd_by_id[representative[source.code]]
                    bootcamp_by_code[source.code] = await self._bootcamp(source, hrd, result)
                hrd_cohort = await self._hrd_cohort(source, hrd_by_id[source.hrd_net_id])
                await self._cohort(source, bootcamp_by_code[source.code], hrd_cohort, result)
            except BusinessRuleViolation as exc:
                logger.info("기수 레코드 %s 건너뜀: %s", source.record_id, exc.code)
                result.unmapped.append(
                    UnmappedRecord(source.record_id, None, str(source.label), exc.code)
                )
        return result

    async def _hrd_bootcamp(
        self, source: CohortSource, cache: dict[str, HrdNetBootcamp]
    ) -> HrdNetBootcamp:
        hrd = cache.get(source.hrd_net_id) or await self._hrd_bootcamps.get_by_hrd_net_id(
            source.hrd_net_id
        )
        if hrd is None:
            hrd = HrdNetBootcamp(name=source.hrd_name, hrd_net_id=source.hrd_net_id)
            await self._hrd_bootcamps.add(hrd)
        elif hrd.name != source.hrd_name.strip():
            hrd = dataclasses.replace(hrd, name=source.hrd_name)
            await self._hrd_bootcamps.save(hrd)
        return hrd

    async def _hrd_cohort(self, source: CohortSource, hrd: HrdNetBootcamp) -> HrdNetBootcampCohort:
        hrd_cohort = await self._hrd_cohorts.get_by_number(hrd.id, source.hrd_round)
        if hrd_cohort is None:
            hrd_cohort = HrdNetBootcampCohort(
                hrd_net_bootcamp_id=hrd.id,
                cohort_number=source.hrd_round,
                train_start_date=source.start_date,
                train_end_date=source.end_date,
            )
            await self._hrd_cohorts.add(hrd_cohort)
        elif (hrd_cohort.train_start_date, hrd_cohort.train_end_date) != (
            source.start_date,
            source.end_date,
        ):
            hrd_cohort = dataclasses.replace(
                hrd_cohort, train_start_date=source.start_date, train_end_date=source.end_date
            )
            await self._hrd_cohorts.save(hrd_cohort)
        return hrd_cohort

    async def _bootcamp(
        self, source: CohortSource, hrd: HrdNetBootcamp, result: MasterSyncResult
    ) -> Bootcamp:
        prefix = source.label.prefix
        bootcamp = await self._bootcamps.get_by_code(source.code)
        holder = await self._bootcamps.get_by_airtable_prefix(prefix)
        if holder is not None and (bootcamp is None or holder.id != bootcamp.id):
            raise BusinessRuleViolation(
                "다른 운영과정이 같은 Airtable 기수 별칭을 쓰고 있습니다.",
                code="airtable_prefix_conflict",
            )
        if bootcamp is None:
            name = (
                prefix
                if await self._bootcamps.get_by_name(prefix) is None
                else f"{prefix} ({source.code})"
            )
            bootcamp = Bootcamp(
                hrd_net_bootcamp_id=hrd.id,
                name=name,
                code=source.code,
                airtable_cohort_prefix=prefix,
            )
            await self._bootcamps.add(bootcamp)
            result.created_bootcamps += 1
        elif bootcamp.airtable_cohort_prefix != prefix:
            bootcamp = dataclasses.replace(bootcamp, airtable_cohort_prefix=prefix)
            await self._bootcamps.save(bootcamp)
        return bootcamp

    async def _cohort(
        self,
        source: CohortSource,
        bootcamp: Bootcamp,
        hrd_cohort: HrdNetBootcampCohort,
        result: MasterSyncResult,
    ) -> None:
        cohort = await self._cohorts.get_by_airtable_record_id(source.record_id)
        if cohort is None:
            cohort = await self._cohorts.get_by_number(bootcamp.id, source.label.number)
        if cohort is None:
            await self._cohorts.add(
                Cohort(
                    hrd_net_cohort_id=hrd_cohort.id,
                    bootcamp_id=bootcamp.id,
                    cohort_number=source.label.number,
                    start_date=source.start_date,
                    end_date=source.end_date,
                    status=source.status or CohortStatus.PLANNED,
                    airtable_record_id=source.record_id,
                )
            )
            result.created_cohorts += 1
            return
        if cohort.bootcamp_id != bootcamp.id or cohort.cohort_number != source.label.number:
            raise BusinessRuleViolation(
                "Airtable 레코드의 과정·기수 번호가 등록된 기수와 다릅니다.",
                code="cohort_record_moved",
            )
        status = cohort.status
        if source.status is not None and cohort.status not in MANUAL_COHORT_STATUSES:
            status = source.status
        updated = dataclasses.replace(
            cohort,
            hrd_net_cohort_id=hrd_cohort.id,
            start_date=source.start_date,
            end_date=source.end_date,
            status=status,
            airtable_record_id=source.record_id,
        )
        if _values(updated) != _values(cohort):
            await self._cohorts.save(updated)
            result.updated_cohorts += 1


def _values(cohort: Cohort) -> tuple[Any, ...]:
    return (
        cohort.hrd_net_cohort_id,
        cohort.start_date,
        cohort.end_date,
        cohort.status,
        cohort.airtable_record_id,
    )


def _representative_hrd(sources: list[CohortSource]) -> dict[str, str]:
    """과정코드별 대표 HRD 과정: 그 코드의 기수가 가장 많이 속한 HRD 과정."""
    counts: dict[str, Counter[str]] = {}
    for source in sources:
        counts.setdefault(source.code, Counter())[source.hrd_net_id] += 1
    return {code: counter.most_common(1)[0][0] for code, counter in counts.items()}

import pytest

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id
from tests.factories.academy import create_cohort

pytestmark = pytest.mark.integration


def catalog() -> AcademyCatalog:
    return AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository())


async def _set_status(cohort_id: object, status: CohortStatus) -> None:
    cohorts = TortoiseCohortRepository()
    cohort = await cohorts.get(cohort_id)  # type: ignore[arg-type]
    assert cohort is not None
    cohort.change_status(status)
    await cohorts.save(cohort)


async def test_staffable_targets_exclude_inactive_bootcamps_and_ended_cohorts() -> None:
    planned = await create_cohort()
    ongoing = await create_cohort()
    await _set_status(ongoing.id, CohortStatus.ONGOING)
    ended = await create_cohort()
    await _set_status(ended.id, CohortStatus.ENDED)
    of_inactive = await create_cohort()
    bootcamps = TortoiseBootcampRepository()
    inactive = await bootcamps.get(of_inactive.bootcamp_id)
    assert inactive is not None
    inactive.is_active = False
    await bootcamps.save(inactive)

    staffable_cohorts = {c.id for c in await catalog().staffable_cohorts()}
    assert staffable_cohorts == {planned.id, ongoing.id}
    staffable_bootcamps = {b.id for b in await catalog().staffable_bootcamps()}
    assert inactive.id not in staffable_bootcamps
    assert planned.bootcamp_id in staffable_bootcamps

    await catalog().ensure_staffable(bootcamp_ids=[planned.bootcamp_id], cohort_ids=[ongoing.id])
    for bootcamp_ids, cohort_ids in (
        ([inactive.id], []),
        ([], [ended.id]),
        ([], [new_id()]),
    ):
        with pytest.raises(BusinessRuleViolation) as exc:
            await catalog().ensure_staffable(bootcamp_ids=bootcamp_ids, cohort_ids=cohort_ids)
        assert exc.value.code == "invalid_staff_target"


async def test_bootcamp_id_of_cohort() -> None:
    cohort = await create_cohort()
    assert await catalog().bootcamp_id_of(cohort.id) == cohort.bootcamp_id
    assert await catalog().bootcamp_id_of(new_id()) is None


async def test_cohorts_in_scope_orders_by_status_then_recent_start() -> None:
    """운영진 '현재 기수' 선택지 (A81): 진행 중 → 예정 → 종료 → 비활성, 최근 시작 순, 보관 제외."""
    import uuid
    from datetime import date

    cohorts = TortoiseCohortRepository()

    async def make(status: CohortStatus, start: date) -> uuid.UUID:
        cohort = await create_cohort()
        cohort.change_status(status)
        cohort.start_date = start
        await cohorts.save(cohort)
        return cohort.id

    ended = await make(CohortStatus.ENDED, date(2026, 5, 1))
    old_ongoing = await make(CohortStatus.ONGOING, date(2026, 9, 1))
    planned = await make(CohortStatus.PLANNED, date(2027, 1, 1))
    new_ongoing = await make(CohortStatus.ONGOING, date(2026, 11, 1))
    inactive = await make(CohortStatus.INACTIVE, date(2026, 10, 1))
    await make(CohortStatus.ARCHIVED, date(2026, 12, 1))

    every = await catalog().cohorts_in_scope(all_cohorts=True)
    assert [c.id for c in every] == [new_ongoing, old_ongoing, planned, ended, inactive]
    assert every[0].bootcamp_name.startswith("운영과정")

    one = await cohorts.get(planned)
    assert one is not None
    by_bootcamp = await catalog().cohorts_in_scope(
        all_cohorts=False, bootcamp_ids={one.bootcamp_id}
    )
    assert [c.id for c in by_bootcamp] == [planned]
    by_cohort = await catalog().cohorts_in_scope(all_cohorts=False, cohort_ids={ended, new_ongoing})
    assert [c.id for c in by_cohort] == [new_ongoing, ended]
    assert await catalog().cohorts_in_scope(all_cohorts=False) == []

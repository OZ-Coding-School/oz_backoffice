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

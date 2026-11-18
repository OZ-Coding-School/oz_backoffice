"""내 수강 등록 목록 조회 (A64)."""

from datetime import date

import pytest

from app.contexts.academy.application.enrollment_queries import EnrollmentQueries
from app.contexts.academy.infrastructure.models import CohortModel
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_user

pytestmark = pytest.mark.integration


def queries() -> EnrollmentQueries:
    return EnrollmentQueries(
        students=TortoiseStudentRepository(),
        cohorts=TortoiseCohortRepository(),
        bootcamps=TortoiseBootcampRepository(),
    )


async def test_latest_cohort_first() -> None:
    user_id = (await create_user()).id
    older, newer = await create_cohort(), await create_cohort()
    await CohortModel.filter(id=older.id).update(
        start_date=date(2025, 3, 1), end_date=date(2025, 8, 31)
    )
    for cohort in (older, newer):
        await TortoiseStudentRepository().add(make_student(cohort_id=cohort.id, user_id=user_id))

    found = await queries().of_user(user_id)

    assert [e.cohort.id for e in found] == [newer.id, older.id]
    assert found[0].bootcamp.id == newer.bootcamp_id
    assert await queries().of_user(new_id()) == []

"""기수 멘토 배정 저장과 DB 제약 (부분 유니크·check)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from tortoise.exceptions import IntegrityError

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
    MentoringPeriodType,
    MentoringSettlementPolicy,
    PayUnit,
)
from app.contexts.mentoring.infrastructure.models import CohortMentorModel
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from tests.factories.academy import create_cohort
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

repo = TortoiseCohortMentorRepository()
NOW = datetime(2026, 11, 10, tzinfo=UTC)


async def _assignment(**overrides: Any) -> CohortMentor:
    values: dict[str, Any] = {
        "period_type": MentoringPeriodType.REGULAR_MENTORING,
        "start_date": date(2026, 11, 1),
        "end_date": date(2026, 12, 31),
        "cost_settlement_policy": MentoringSettlementPolicy.ACTUAL_DURATION,
        "pay_unit": PayUnit.HOURLY,
        "pay_rate": 30000,
    }
    values.update(overrides)
    if "cohort_id" not in values:
        values["cohort_id"] = (await create_cohort()).id
    if "mentor_id" not in values:
        values["mentor_id"] = (await create_mentor()).id
    entity = CohortMentor(**values)
    await repo.add(entity)
    return entity


async def test_one_active_assignment_per_mentor_cohort_type() -> None:
    first = await _assignment()
    keys = {"cohort_id": first.cohort_id, "mentor_id": first.mentor_id}
    await _assignment(**keys, period_type=MentoringPeriodType.PROJECT_MENTORING)  # 다른 유형
    with pytest.raises(IntegrityError):
        await _assignment(**keys)

    first.deactivate(CohortMentorDeactivationReason.MANUAL, now=NOW)
    await repo.save(first)
    second = await _assignment(**keys)  # 비활성이면 다시 배정 가능
    found = await repo.find_active(
        first.mentor_id, first.cohort_id, MentoringPeriodType.REGULAR_MENTORING
    )
    assert found is not None
    assert found.id == second.id
    assert len(await repo.list_by_cohort(first.cohort_id, include_inactive=True)) == 3
    assert len(await repo.list_by_cohort(first.cohort_id, include_inactive=False)) == 2
    assert len(await repo.list_by_mentor(first.mentor_id, include_inactive=False)) == 2


async def test_open_ended_and_expired_listing() -> None:
    open_ended = await _assignment(end_date=None)
    ended = await _assignment(end_date=date(2026, 11, 9))
    await _assignment(end_date=date(2026, 11, 10))  # 당일까지 활성
    loaded = await repo.get(open_ended.id)
    assert loaded is not None
    assert loaded.end_date is None
    assert [a.id for a in await repo.list_expired(date(2026, 11, 10))] == [ended.id]


@pytest.mark.parametrize(
    "values",
    [
        {"pay_unit": "MONTHLY"},
        {"end_date": date(2026, 10, 1)},
        {"pay_rate": -1},
        {"is_active": False},  # 비활성 시각·사유 없음
        {"deactivation_reason": "MANUAL"},  # 활성인데 사유
    ],
)
async def test_db_checks(values: dict[str, Any]) -> None:
    data: dict[str, Any] = {
        "cohort_id": (await create_cohort()).id,
        "mentor_id": (await create_mentor()).id,
        "period_type": "REGULAR_MENTORING",
        "start_date": date(2026, 11, 1),
        "cost_settlement_policy": "ACTUAL_DURATION",
        "pay_unit": "HOURLY",
        "pay_rate": 0,
    }
    data.update(values)
    with pytest.raises(IntegrityError):
        await CohortMentorModel.create(**data)

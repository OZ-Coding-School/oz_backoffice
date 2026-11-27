"""기수 멘토 배정 저장과 DB 제약 (부분 유니크·check)."""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from tortoise.exceptions import IntegrityError

from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import CohortMentorDeactivationReason
from app.contexts.mentoring.infrastructure.models import CohortMentorModel
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.shared.errors import ConflictError
from tests.factories.academy import create_cohort
from tests.factories.educator import create_mentor, create_mentor_contract

pytestmark = pytest.mark.integration

repo = TortoiseCohortMentorRepository()
NOW = datetime(2026, 11, 10, tzinfo=UTC)


async def _assignment(**overrides: Any) -> CohortMentor:
    values: dict[str, Any] = {
        "start_date": date(2026, 11, 1),
        "end_date": date(2026, 12, 31),
    }
    values.update(overrides)
    cohort = await create_cohort()
    if "cohort_id" not in values:
        values["cohort_id"] = cohort.id
    if "mentor_id" not in values:
        values["mentor_id"] = (await create_mentor()).id
    if "contract_id" not in values:
        contract = await create_mentor_contract(values["mentor_id"], bootcamp_id=cohort.bootcamp_id)
        values["contract_id"] = contract.id
    entity = CohortMentor(**values)
    await repo.add(entity)
    return entity


async def test_one_active_assignment_per_mentor_cohort() -> None:
    first = await _assignment()
    keys = {"cohort_id": first.cohort_id, "mentor_id": first.mentor_id}
    await _assignment(mentor_id=first.mentor_id)  # 다른 기수는 따로 (A41)
    with pytest.raises(ConflictError) as dup:  # 부분 유니크 위반은 409로 바꾼다
        await _assignment(**keys)
    assert dup.value.code == "assignment_already_exists"

    first.deactivate(CohortMentorDeactivationReason.MANUAL, now=NOW)
    await repo.save(first)
    second = await _assignment(**keys)  # 비활성이면 다시 배정 가능
    found = await repo.find_active(first.mentor_id, first.cohort_id)
    assert found is not None
    assert found.id == second.id
    assert len(await repo.list_by_cohort(first.cohort_id, include_inactive=True)) == 2
    assert len(await repo.list_by_cohort(first.cohort_id, include_inactive=False)) == 1
    assert len(await repo.list_by_mentor(first.mentor_id, include_inactive=False)) == 2


async def test_open_ended_and_expired_listing() -> None:
    open_ended = await _assignment(end_date=None)
    ended = await _assignment(end_date=date(2026, 11, 9))
    await _assignment(end_date=date(2026, 11, 10))  # 당일까지 활성
    loaded = await repo.get(open_ended.id)
    assert loaded is not None
    assert loaded.end_date is None
    assert [a.id for a in await repo.list_expired(date(2026, 11, 10))] == [ended.id]
    assert {a.id for a in await repo.list_active_by_contract(ended.contract_id)} == {ended.id}


@pytest.mark.parametrize(
    "values",
    [
        {"end_date": date(2026, 10, 1)},
        {"is_active": False},  # 비활성 시각·사유 없음
        {"deactivation_reason": "MANUAL"},  # 활성인데 사유
    ],
)
async def test_db_checks(values: dict[str, Any]) -> None:
    cohort = await create_cohort()
    mentor = await create_mentor()
    contract = await create_mentor_contract(mentor.id, bootcamp_id=cohort.bootcamp_id)
    data: dict[str, Any] = {
        "cohort_id": cohort.id,
        "mentor_id": mentor.id,
        "contract_id": contract.id,
        "start_date": date(2026, 11, 1),
    }
    data.update(values)
    with pytest.raises(IntegrityError):
        await CohortMentorModel.create(**data)

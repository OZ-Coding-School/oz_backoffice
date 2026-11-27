from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, ContractType, TerminationReason
from app.contexts.educator.domain.repositories import ContractFilter, ContractVisibility
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractFileRepository,
    TortoiseEducatorContractRepository,
)
from app.shared.ids import new_id
from tests.factories.educator import INSTRUCTOR_TERMS, create_mentor, mentor_contract_fields
from tests.factories.organization import create_employee

pytestmark = pytest.mark.integration

contracts = TortoiseEducatorContractRepository()
files = TortoiseContractFileRepository()


async def _file() -> ContractFile:
    file = ContractFile(
        file_name="계약서.pdf",
        file_ext="pdf",
        file_size=10,
        storage_key=f"contracts/{new_id()}.pdf",
    )
    await files.add(file)
    return file


async def _contract(**overrides: Any) -> EducatorContract:
    values: dict[str, Any] = {
        "manager_employee_id": (await create_employee()).id,
        **(await mentor_contract_fields()),
        "contractor_name": "김멘토",
        "contractor_phone": "01012345678",
        "title": "2026 멘토 계약",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
    }
    values.update(overrides)
    if values.get("status", ContractStatus.DRAFT) is not ContractStatus.DRAFT:
        values.setdefault("contract_file_id", (await _file()).id)
    if values.get("status") in (
        ContractStatus.SIGNED,
        ContractStatus.ACTIVE,
        ContractStatus.ENDED,
        ContractStatus.TERMINATED,
    ):
        values.setdefault("signed_contract_file_id", (await _file()).id)
        if values.get("contract_type", ContractType.MENTOR) is ContractType.MENTOR:
            values.setdefault("mentor_id", (await create_mentor()).id)  # 완료부터 멘토 필수 (A115)
    contract = EducatorContract(**values)
    await contracts.add(contract)
    return contract


async def test_round_trip_and_file_lookup() -> None:
    file = await _file()
    contract = await _contract(contract_file_id=file.id, contractor_email="a@b.com")

    loaded = await contracts.get(contract.id)
    assert loaded is not None
    assert (loaded.contract_file_id, loaded.contractor_email) == (file.id, "a@b.com")
    assert loaded.created_at is not None
    assert (await contracts.get_by_file(file.id)) == contract

    file.discard(now=datetime(2026, 11, 9, tzinfo=UTC))
    await files.save(file)
    saved = await files.get(file.id)
    assert saved is not None
    assert saved.deleted_at is not None
    assert saved.created_at is not None


async def test_list_filters_and_search() -> None:
    draft = await _contract(contractor_name="김멘토", title="백엔드 멘토")
    active = await _contract(
        contractor_name="박강사",
        contractor_phone="01099998888",
        title="강의 계약",
        **INSTRUCTOR_TERMS,
        status=ContractStatus.ACTIVE,
    )
    ended = await _contract(contractor_name="이멘토", status=ContractStatus.ENDED)

    async def ids(**kwargs: Any) -> list[object]:
        page, _ = await contracts.list_page(ContractFilter(**kwargs), limit=20, offset=0)
        return [c.id for c in page]

    assert await ids() == [ended.id, active.id, draft.id]  # 최근 등록 순
    assert await ids(statuses=frozenset({ContractStatus.ACTIVE, ContractStatus.ENDED})) == [
        ended.id,
        active.id,
    ]
    assert await ids(contract_types=frozenset({ContractType.INSTRUCTOR})) == [active.id]
    assert await ids(query="멘토") == [ended.id, draft.id]  # 이름·제목
    assert await ids(query="9999-8888") == [active.id]  # 휴대폰 (숫자만 비교)
    page, total = await contracts.list_page(ContractFilter(), limit=1, offset=1)
    assert ([c.id for c in page], total) == ([active.id], 3)


async def test_list_due() -> None:
    today = date(2026, 11, 9)
    expired = await _contract(status=ContractStatus.ACTIVE, end_date=date(2026, 11, 8))
    starting = await _contract(status=ContractStatus.SIGNED, start_date=today)
    open_start = await _contract(status=ContractStatus.SIGNED, start_date=None)
    await _contract(status=ContractStatus.SIGNED, start_date=date(2026, 11, 10))  # 시작 전
    await _contract(status=ContractStatus.ACTIVE, end_date=today)  # 당일까지는 유효
    await _contract(status=ContractStatus.ACTIVE, end_date=None)  # 종료일 없음
    await _contract(status=ContractStatus.TERMINATED, end_date=date(2026, 1, 31), **_TERMINATED)
    await _contract(end_date=date(2026, 1, 31))  # DRAFT

    assert {c.id for c in await contracts.list_due(today)} == {
        expired.id,
        starting.id,
        open_start.id,
    }


_TERMINATED: dict[str, Any] = {
    "termination_reason": TerminationReason.TERMINATED_BY_FAULT,
    "terminated_on": date(2026, 1, 15),
}


async def test_list_filters_by_academy_and_visibility() -> None:
    cohort = await _contract()  # 기수 계약
    common = await _contract(bootcamp_id=cohort.bootcamp_id, cohort_id=None)  # 과정 공통
    other = await _contract()  # 다른 과정

    async def ids(**kwargs: Any) -> set[object]:
        page, _ = await contracts.list_page(ContractFilter(**kwargs), limit=20, offset=0)
        return {c.id for c in page}

    assert await ids(bootcamp_id=cohort.bootcamp_id) == {cohort.id, common.id}
    assert await ids(cohort_id=other.cohort_id) == {other.id}
    by_bootcamp = ContractVisibility(bootcamp_ids=frozenset({cohort.bootcamp_id}))
    assert await ids(visible=by_bootcamp) == {cohort.id, common.id}
    assert other.cohort_id is not None
    by_cohort = ContractVisibility(cohort_ids=frozenset({other.cohort_id}))
    assert await ids(visible=by_cohort) == {other.id}
    assert await ids(visible=ContractVisibility()) == set()
    # A112: 기수 + 같은 과정의 과정 공통
    assert await ids(cohort_id=cohort.cohort_id, common_bootcamp_id=cohort.bootcamp_id) == {
        cohort.id,
        common.id,
    }
    counts = await contracts.count_by_types(ContractFilter(bootcamp_id=cohort.bootcamp_id))
    assert sum(counts.values()) == 2
    assert await contracts.count_by_types(
        ContractFilter(visible=ContractVisibility())
    ) == dict.fromkeys(counts, 0)

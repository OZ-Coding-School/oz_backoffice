from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractFileRepository,
    TortoiseEducatorContractRepository,
)
from app.shared.ids import new_id
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
        "educator_type": EducatorType.MENTOR,
        "contractor_name": "김멘토",
        "contractor_phone": "01012345678",
        "title": "2026 멘토 계약",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
    }
    values.update(overrides)
    if values.get("status", ContractStatus.DRAFT) is not ContractStatus.DRAFT:
        values.setdefault("contract_file_id", (await _file()).id)
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
        educator_type=EducatorType.INSTRUCTOR,
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
    assert await ids(educator_type=EducatorType.INSTRUCTOR) == [active.id]
    assert await ids(query="멘토") == [ended.id, draft.id]  # 이름·제목
    assert await ids(query="9999-8888") == [active.id]  # 휴대폰 (숫자만 비교)
    page, total = await contracts.list_page(ContractFilter(), limit=1, offset=1)
    assert ([c.id for c in page], total) == ([active.id], 3)


async def test_list_active_ended_before() -> None:
    today = date(2026, 11, 9)
    expired = await _contract(status=ContractStatus.ACTIVE, end_date=date(2026, 11, 8))
    await _contract(status=ContractStatus.ACTIVE, end_date=today)  # 당일까지는 유효
    await _contract(status=ContractStatus.TERMINATED, end_date=date(2026, 1, 31))
    await _contract(end_date=date(2026, 1, 31))  # DRAFT

    assert [c.id for c in await contracts.list_active_ended_before(today)] == [expired.id]

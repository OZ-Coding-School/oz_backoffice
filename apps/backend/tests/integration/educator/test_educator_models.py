"""educator 테이블의 DB 제약 (마이그레이션 raw SQL check, 기본값, 유니크)."""

import uuid
from datetime import date
from typing import Any

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.educator.domain.enums import ContractStatus, DisplayNamePreference, EducatorType
from app.contexts.educator.infrastructure.models import (
    ContractFileModel,
    EducatorContractModel,
    InstructorModel,
    MentorModel,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.factories.organization import create_employee

pytestmark = pytest.mark.integration


async def _user_id() -> uuid.UUID:
    user = make_user()
    await TortoiseUserRepository().add(user)
    return user.id


async def _file() -> ContractFileModel:
    return await ContractFileModel.create(
        file_name="계약서.pdf",
        file_ext="pdf",
        file_size=1024,
        storage_key=f"contracts/{new_id()}.pdf",
    )


async def _contract(**overrides: Any) -> EducatorContractModel:
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
    return await EducatorContractModel.create(**values)


async def _raw_insert_defaults(table: str, user_id: uuid.UUID) -> dict[str, Any]:
    """DB 기본값만으로 행을 만든다 (Tortoise 기본값이 아니라 마이그레이션의 DEFAULT 확인)."""
    conn = connections.get("default")
    await conn.execute_query(
        f'INSERT INTO "{table}" ("id", "user_id") VALUES ($1, $2)', [new_id(), user_id]
    )
    _, rows = await conn.execute_query(f'SELECT * FROM "{table}" WHERE "user_id" = $1', [user_id])
    return dict(rows[0])


@pytest.mark.parametrize("table", ["mentors", "instructors"])
async def test_profile_db_defaults(table: str) -> None:
    row = await _raw_insert_defaults(table, await _user_id())
    assert row["display_name_preference"] == "NAME"
    assert row["created_at"] is not None
    if table == "mentors":
        assert row["is_active"] is True


@pytest.mark.parametrize("model", [MentorModel, InstructorModel])
async def test_nickname_display_requires_nickname(
    model: type[MentorModel] | type[InstructorModel],
) -> None:
    await model.create(
        user_id=await _user_id(),
        nickname="오즈",
        display_name_preference=DisplayNamePreference.NICKNAME,
    )
    with pytest.raises(IntegrityError):
        await model.create(
            user_id=await _user_id(), display_name_preference=DisplayNamePreference.NICKNAME
        )


async def test_one_profile_per_user() -> None:
    user_id = await _user_id()
    await MentorModel.create(user_id=user_id)
    with pytest.raises(IntegrityError):
        await MentorModel.create(user_id=user_id)


async def test_draft_contract_without_file_but_active_requires_file() -> None:
    draft = await _contract()
    assert draft.status is ContractStatus.DRAFT
    assert draft.contract_file_id is None  # type: ignore[attr-defined]  # Tortoise FK 컬럼 속성

    with pytest.raises(IntegrityError):
        await _contract(status=ContractStatus.ACTIVE)
    active = await _contract(status=ContractStatus.ACTIVE, contract_file_id=(await _file()).id)
    assert active.status is ContractStatus.ACTIVE


async def test_contract_file_belongs_to_one_contract() -> None:
    file = await _file()
    await _contract(contract_file_id=file.id)
    with pytest.raises(IntegrityError):
        await _contract(contract_file_id=file.id)


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_date": date(2026, 2, 1), "end_date": date(2026, 1, 31)},  # 기간 역전
        {"contractor_email": "Mentor@Example.com"},  # 소문자 정규화
    ],
)
async def test_contract_checks(overrides: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        await _contract(**overrides)


async def test_contract_link_must_match_educator_type() -> None:
    mentor = await MentorModel.create(user_id=await _user_id())
    instructor = await InstructorModel.create(user_id=await _user_id())

    await _contract(mentor_id=mentor.id)
    await _contract(educator_type=EducatorType.INSTRUCTOR, instructor_id=instructor.id)
    with pytest.raises(IntegrityError):
        await _contract(educator_type=EducatorType.INSTRUCTOR, mentor_id=mentor.id)
    with pytest.raises(IntegrityError):
        await _contract(instructor_id=instructor.id)


async def test_contract_db_defaults() -> None:
    conn = connections.get("default")
    contract_id = new_id()
    await conn.execute_query(
        'INSERT INTO "educator_contracts" ("id", "manager_employee_id", "educator_type",'
        ' "contractor_name", "contractor_phone", "title", "start_date", "end_date")'
        " VALUES ($1, $2, 'MENTOR', '김멘토', '01012345678', '계약', '2026-01-01', '2026-12-31')",
        [contract_id, (await create_employee()).id],
    )
    _, rows = await conn.execute_query(
        'SELECT "status", "created_at" FROM "educator_contracts" WHERE "id" = $1', [contract_id]
    )
    assert rows[0]["status"] == "DRAFT"
    assert rows[0]["created_at"] is not None

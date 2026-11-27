"""educator 테이블의 DB 제약 (마이그레이션 raw SQL check, 기본값, 유니크)."""

import uuid
from datetime import date
from typing import Any

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.educator.domain.enums import (
    ContractStatus,
    ContractType,
    DisplayNamePreference,
    PriceUnit,
    SettlementType,
    TerminationReason,
)
from app.contexts.educator.infrastructure.models import (
    ContractFileModel,
    EducatorContractModel,
    InstructorModel,
    MentorModel,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.shared.ids import new_id
from tests.factories.educator import INSTRUCTOR_TERMS, mentor_contract_fields
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
        **(await mentor_contract_fields()),
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


async def test_file_required_from_in_progress() -> None:
    """계약서는 IN_PROGRESS부터 필수 (A109⑥). 초안에서 바로 취소한 계약은 없어도 된다."""
    draft = await _contract()
    assert draft.status is ContractStatus.DRAFT
    assert draft.contract_file_id is None  # type: ignore[attr-defined]  # Tortoise FK 컬럼 속성

    with pytest.raises(IntegrityError):
        await _contract(status=ContractStatus.IN_PROGRESS)
    await _contract(
        status=ContractStatus.CANCELED, cancel_reason="취소", canceled_on=date(2026, 1, 2)
    )
    active = await _contract(status=ContractStatus.ACTIVE, contract_file_id=(await _file()).id)
    assert active.status is ContractStatus.ACTIVE


async def test_contract_file_belongs_to_one_contract() -> None:
    file = await _file()
    await _contract(contract_file_id=file.id)
    with pytest.raises(IntegrityError):
        await _contract(contract_file_id=file.id)


_VENDOR: dict[str, Any] = {
    "contract_type": ContractType.SW,
    "settlement_type": SettlementType.FIXED,
    "total_amount": 1000,
    "unit_price": None,
    "price_unit": None,
    "no_show_pay_amount": None,
    "mentoring_time_basis": None,
    "contractor_phone": None,
}


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_date": date(2026, 2, 1), "end_date": date(2026, 1, 31)},  # 기간 역전
        {"contractor_email": "Mentor@Example.com"},  # 소문자 정규화
        {"price_unit": PriceUnit.MONTHLY},  # 멘토는 시간·회 단가만
        {"no_show_pay_amount": None},  # 멘토 전용 칸 필수
        {"unit_price": None},  # 단가 계약은 단가 필수
        {"unit_price": -1},
        {"contractor_phone": "021234567"},  # 멘토는 휴대폰
        {"business_registration_number": "1234567890"},  # 멘토는 업체 칸 없음
        {"status": ContractStatus.CANCELED},  # 취소 사유·일자 필요
        {"cancel_reason": "취소", "canceled_on": date(2026, 1, 2)},  # 취소가 아닌데 사유
        {
            "status": ContractStatus.TERMINATED,
            "termination_reason": TerminationReason.TERMINATED_BY_FAULT,
        },  # 해지 일자 필요
        {**_VENDOR, "total_amount": None},  # 정액은 총액 필수
        {**_VENDOR, "no_show_pay_amount": 0},  # 멘토가 아니면 노쇼 금액 없음
        {**_VENDOR, "business_registration_number": "123"},
        {**_VENDOR, "contractor_phone": "123"},
    ],
)
async def test_contract_checks(overrides: dict[str, Any]) -> None:
    if overrides.get("status") in (ContractStatus.TERMINATED,):
        overrides = {**overrides, "contract_file_id": (await _file()).id}
    with pytest.raises(IntegrityError):
        await _contract(**overrides)


async def test_vendor_contract_rows() -> None:
    await _contract(**_VENDOR, cohort_id=None)
    await _contract(
        **{
            **_VENDOR,
            "settlement_type": SettlementType.ACTUAL_COST,
            "total_amount": None,
            "contractor_phone": "021234567",
            "business_registration_number": "1234567890",
        }
    )
    await _contract(
        **{
            **_VENDOR,
            "settlement_type": SettlementType.UNIT_PRICE,
            "unit_price": 10,
            "price_unit": PriceUnit.MONTHLY,
        }
    )


async def test_contract_link_must_match_contract_type() -> None:
    mentor = await MentorModel.create(user_id=await _user_id())
    instructor = await InstructorModel.create(user_id=await _user_id())

    await _contract(mentor_id=mentor.id)
    await _contract(**INSTRUCTOR_TERMS, instructor_id=instructor.id)
    with pytest.raises(IntegrityError):
        await _contract(**INSTRUCTOR_TERMS, mentor_id=mentor.id)
    with pytest.raises(IntegrityError):
        await _contract(instructor_id=instructor.id)


async def test_contract_enum_checks() -> None:
    conn = connections.get("default")
    row = await _contract()
    for column, value in (("status", "UNKNOWN"), ("contract_type", "CAR"), ("vat_type", "X")):
        with pytest.raises(IntegrityError):
            await conn.execute_query(
                f'UPDATE "educator_contracts" SET "{column}" = $1 WHERE "id" = $2', [value, row.id]
            )


async def test_contract_db_defaults() -> None:
    conn = connections.get("default")
    contract_id = new_id()
    fields = await mentor_contract_fields()
    await conn.execute_query(
        'INSERT INTO "educator_contracts" ("id", "manager_employee_id", "contract_type",'
        ' "bootcamp_id", "contractor_name", "contractor_phone", "title", "settlement_type",'
        ' "unit_price", "price_unit", "vat_type", "no_show_pay_amount", "mentoring_time_basis")'
        " VALUES ($1, $2, 'MENTOR', $3, '김멘토', '01012345678', '계약', 'UNIT_PRICE',"
        " 50000, 'HOURLY', 'NOT_APPLICABLE', 0, 'ACTUAL_DURATION')",
        [contract_id, (await create_employee()).id, fields["bootcamp_id"]],
    )
    _, rows = await conn.execute_query(
        'SELECT "status", "created_at" FROM "educator_contracts" WHERE "id" = $1', [contract_id]
    )
    assert rows[0]["status"] == "DRAFT"
    assert rows[0]["created_at"] is not None

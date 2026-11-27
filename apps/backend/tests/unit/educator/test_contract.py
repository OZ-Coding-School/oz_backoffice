from datetime import date
from typing import Any

import pytest

from app.contexts.educator.domain.entities import ContractAmendment, EducatorContract
from app.contexts.educator.domain.enums import (
    ContractStatus,
    ContractType,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    TerminationReason,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 9)


def make_contract(**overrides: Any) -> EducatorContract:
    values: dict[str, Any] = {
        "manager_employee_id": new_id(),
        "contract_type": ContractType.MENTOR,
        "bootcamp_id": new_id(),
        "contractor_name": " 김멘토 ",
        "contractor_phone": "010-1234-5678",
        "contractor_email": " Mentor@Example.COM ",
        "title": " 2026 멘토 계약 ",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "settlement_type": SettlementType.UNIT_PRICE,
        "unit_price": 50000,
        "price_unit": PriceUnit.HOURLY,
        "no_show_pay_amount": 10000,
        "mentoring_time_basis": MentoringTimeBasis.ACTUAL_DURATION,
    }
    values.update(overrides)
    return EducatorContract(**values)


def make_vendor(**overrides: Any) -> EducatorContract:
    values: dict[str, Any] = {
        "contract_type": ContractType.SW,
        "contractor_name": "(주)오즈",
        "contractor_phone": "02-123-4567",
        "settlement_type": SettlementType.FIXED,
        "total_amount": 1_200_000,
        "unit_price": None,
        "price_unit": None,
        "no_show_pay_amount": None,
        "mentoring_time_basis": None,
    }
    values.update(overrides)
    return make_contract(**values)


def signed(**overrides: Any) -> EducatorContract:
    contract = make_contract(contract_file_id=new_id(), **overrides)
    contract.start_progress()
    contract.sign(today=TODAY)
    return contract


def test_contract_is_normalized_and_starts_as_draft() -> None:
    contract = make_contract()
    assert (contract.contractor_name, contract.contractor_phone) == ("김멘토", "01012345678")
    assert contract.contractor_email == "mentor@example.com"
    assert contract.title == "2026 멘토 계약"
    assert contract.status is ContractStatus.DRAFT
    assert make_contract(contractor_email="  ").contractor_email is None


def test_vendor_contract_party() -> None:
    vendor = make_vendor(business_registration_number="123-45-67890", contact_person_name=" 박 ")
    assert (vendor.contractor_phone, vendor.business_registration_number) == (
        "021234567",
        "1234567890",
    )
    assert vendor.contact_person_name == "박"
    assert make_vendor(contractor_phone=None).contractor_phone is None


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"start_date": date(2026, 2, 1), "end_date": date(2026, 1, 31)},
            "invalid_contract_period",
        ),
        ({"title": "  "}, "invalid_contract_title"),
        ({"title": "가" * 101}, "invalid_contract_title"),
        ({"contractor_phone": "02-123-4567"}, "invalid_phone_number"),  # 멘토는 휴대폰
        ({"contractor_phone": None}, "invalid_phone_number"),
        ({"contractor_email": "not-an-email"}, "invalid_email"),
        ({"contractor_name": ""}, "invalid_name"),
        ({"business_registration_number": "1234567890"}, "invalid_contract_party"),
        ({"price_unit": PriceUnit.MONTHLY}, "invalid_mentor_contract_terms"),
        ({"no_show_pay_amount": None}, "invalid_mentor_contract_terms"),
        ({"mentoring_time_basis": None}, "invalid_mentor_contract_terms"),
        ({"unit_price": -1}, "invalid_contract_amount"),
        ({"unit_price": None}, "invalid_contract_amount"),
        (
            {
                "settlement_type": SettlementType.FIXED,
                "total_amount": 100,
                "unit_price": None,
                "price_unit": None,
            },
            "invalid_mentor_contract_terms",  # 멘토는 항상 단가
        ),
    ],
)
def test_contract_validation(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        make_contract(**overrides)
    assert exc.value.code == code


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"total_amount": None}, "invalid_contract_amount"),  # 정액은 총액 필수
        ({"unit_price": 100}, "invalid_contract_amount"),  # 단가는 단가 계약만
        ({"no_show_pay_amount": 0}, "invalid_mentor_contract_terms"),
        ({"contractor_phone": "1234"}, "invalid_phone_number"),
        ({"business_registration_number": "123"}, "invalid_business_registration_number"),
        (
            {"settlement_type": SettlementType.UNIT_PRICE, "total_amount": None, "unit_price": 1},
            "invalid_contract_amount",  # 단가 기준 없음
        ),
    ],
)
def test_vendor_validation(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        make_vendor(**overrides)
    assert exc.value.code == code


def test_amounts_by_settlement_type() -> None:
    assert (
        make_vendor(settlement_type=SettlementType.ACTUAL_COST, total_amount=None).total_amount
        is None
    )
    monthly = make_vendor(
        settlement_type=SettlementType.UNIT_PRICE,
        unit_price=300000,
        price_unit=PriceUnit.MONTHLY,
        total_amount=None,
    )
    assert monthly.price_unit is PriceUnit.MONTHLY


def test_period_is_optional() -> None:
    assert make_contract(start_date=None, end_date=None).start_date is None
    assert make_contract(start_date=TODAY, end_date=TODAY).end_date == TODAY


def test_editable_until_signed() -> None:
    contract = make_contract()
    revised = contract.revised({"title": "변경", "contract_file_id": new_id()})
    assert (revised.id, revised.title) == (contract.id, "변경")
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.revised({"end_date": date(2025, 1, 1)})
    assert exc.value.code == "invalid_contract_period"

    progressing = make_contract(contract_file_id=new_id())
    progressing.start_progress()
    assert progressing.revised({"unit_price": 60000}).unit_price == 60000
    with pytest.raises(BusinessRuleViolation) as file:  # 진행 중부터 계약서 필수
        progressing.revised({"contract_file_id": None})
    assert file.value.code == "contract_file_required"


@pytest.mark.parametrize(
    "status",
    [ContractStatus.SIGNED, ContractStatus.ACTIVE, ContractStatus.ENDED, ContractStatus.TERMINATED],
)
def test_signed_contract_only_changes_manager(status: ContractStatus) -> None:
    contract = make_contract(contract_file_id=new_id(), status=status)
    manager = new_id()

    assert contract.revised({"manager_employee_id": manager}).manager_employee_id == manager
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.revised({"manager_employee_id": manager, "title": "변경"})
    assert exc.value.code == "contract_not_editable"


def test_progress_requires_file() -> None:
    contract = make_contract()
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.start_progress()
    assert exc.value.code == "contract_file_required"
    with pytest.raises(BusinessRuleViolation) as skip:  # 진행을 건너뛰고 완료할 수 없다
        make_contract(contract_file_id=new_id()).sign(today=TODAY)
    assert skip.value.code == "invalid_contract_transition"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (None, None, ContractStatus.ACTIVE),  # 기간이 없으면 바로 이행
        (TODAY, None, ContractStatus.ACTIVE),  # 시작일 당일
        (date(2026, 11, 10), None, ContractStatus.SIGNED),  # 시작 전
        (date(2026, 1, 1), TODAY, ContractStatus.ACTIVE),  # 종료일 당일까지는 ACTIVE
        (date(2026, 1, 1), date(2026, 11, 8), ContractStatus.ENDED),  # 이미 끝난 계약
    ],
)
def test_sign(start: date | None, end: date | None, expected: ContractStatus) -> None:
    assert signed(start_date=start, end_date=end).status is expected


def test_advance_by_date() -> None:
    contract = signed(start_date=date(2026, 11, 10), end_date=date(2026, 11, 11))
    assert contract.advance(today=TODAY) is False
    assert contract.advance(today=date(2026, 11, 10)) is True
    statuses = [contract.status]
    assert contract.advance(today=date(2026, 11, 11)) is False
    assert contract.advance(today=date(2026, 11, 12)) is True
    statuses.append(contract.status)
    assert statuses == [ContractStatus.ACTIVE, ContractStatus.ENDED]
    assert contract.advance(today=date(2030, 1, 1)) is False


def test_end_only_without_end_date() -> None:
    contract = signed(start_date=None, end_date=None)
    contract.end()
    assert contract.status is ContractStatus.ENDED
    with pytest.raises(BusinessRuleViolation) as has_end:
        signed().end()
    assert has_end.value.code == "contract_has_end_date"


def test_cancel_before_sign() -> None:
    contract = make_contract()
    with pytest.raises(BusinessRuleViolation) as no_reason:
        contract.cancel(reason="  ", on=TODAY)
    assert no_reason.value.code == "invalid_cancel_reason"
    contract.cancel(reason=" 조건 불일치 ", on=TODAY)
    assert (contract.status, contract.cancel_reason, contract.canceled_on) == (
        ContractStatus.CANCELED,
        "조건 불일치",
        TODAY,
    )
    with pytest.raises(BusinessRuleViolation) as after_sign:
        signed().cancel(reason="취소", on=TODAY)
    assert after_sign.value.code == "invalid_contract_transition"


def test_terminate_after_sign() -> None:
    with pytest.raises(BusinessRuleViolation):
        make_contract().terminate(
            reason=TerminationReason.TERMINATED_BY_FAULT, detail=None, on=TODAY
        )
    contract = signed()
    contract.terminate(
        reason=TerminationReason.TERMINATED_BY_MUTUAL_AGREEMENT, detail=" 합의 ", on=TODAY
    )
    assert (contract.status, contract.termination_detail, contract.terminated_on) == (
        ContractStatus.TERMINATED,
        "합의",
        TODAY,
    )
    assert contract.advance(today=date(2030, 1, 1)) is False  # 해지된 계약은 넘기지 않는다


def test_amend_only_after_sign_and_allowed_fields() -> None:
    contract = signed()
    amended = contract.amended({"unit_price": 70000, "end_date": date(2027, 6, 30)})
    assert (amended.unit_price, amended.end_date) == (70000, date(2027, 6, 30))
    with pytest.raises(BusinessRuleViolation) as kind:
        contract.amended({"cohort_id": new_id()})
    assert kind.value.code == "contract_field_not_amendable"
    with pytest.raises(BusinessRuleViolation) as empty:
        contract.amended({})
    assert empty.value.code == "amendment_no_changes"
    with pytest.raises(BusinessRuleViolation) as draft:
        make_contract().amended({"title": "변경"})
    assert draft.value.code == "invalid_contract_transition"
    with pytest.raises(BusinessRuleViolation) as rule:  # 바뀐 값도 같은 규칙으로 검사
        contract.amended({"price_unit": PriceUnit.DAILY})
    assert rule.value.code == "invalid_mentor_contract_terms"


def test_amendment_requires_reason() -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        ContractAmendment(
            contract_id=new_id(),
            amended_on=TODAY,
            reason=" ",
            before={},
            after={},
            created_by_user_id=new_id(),
        )
    assert exc.value.code == "invalid_amendment_reason"


def test_only_draft_is_deletable() -> None:
    make_contract().ensure_deletable()
    contract = make_contract(contract_file_id=new_id(), status=ContractStatus.IN_PROGRESS)
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.ensure_deletable()
    assert exc.value.code == "contract_not_deletable"


def test_link_matches_contract_type() -> None:
    vendor = make_vendor()
    with pytest.raises(BusinessRuleViolation) as exc:
        vendor.link(mentor_id=new_id(), instructor_id=None)
    assert exc.value.code == "contract_type_mismatch"
    vendor.link(mentor_id=None, instructor_id=None)

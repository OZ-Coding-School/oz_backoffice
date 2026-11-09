from datetime import date
from typing import Any

import pytest

from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 9)


def make_contract(**overrides: Any) -> EducatorContract:
    values: dict[str, Any] = {
        "manager_employee_id": new_id(),
        "educator_type": EducatorType.MENTOR,
        "contractor_name": " 김멘토 ",
        "contractor_phone": "010-1234-5678",
        "contractor_email": " Mentor@Example.COM ",
        "title": " 2026 멘토 계약 ",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
    }
    values.update(overrides)
    return EducatorContract(**values)


def test_contract_is_normalized_and_starts_as_draft() -> None:
    contract = make_contract()
    assert (contract.contractor_name, contract.contractor_phone) == ("김멘토", "01012345678")
    assert contract.contractor_email == "mentor@example.com"
    assert contract.title == "2026 멘토 계약"
    assert contract.status is ContractStatus.DRAFT
    assert make_contract(contractor_email="  ").contractor_email is None


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"start_date": date(2026, 2, 1), "end_date": date(2026, 1, 31)},
            "invalid_contract_period",
        ),
        ({"title": "  "}, "invalid_contract_title"),
        ({"title": "가" * 101}, "invalid_contract_title"),
        ({"contractor_phone": "02-123-4567"}, "invalid_phone_number"),
        ({"contractor_email": "not-an-email"}, "invalid_email"),
        ({"contractor_name": ""}, "invalid_name"),
    ],
)
def test_contract_validation(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        make_contract(**overrides)
    assert exc.value.code == code


def test_same_day_period_is_allowed() -> None:
    assert make_contract(start_date=TODAY, end_date=TODAY).end_date == TODAY


def test_draft_can_be_revised_with_validation() -> None:
    contract = make_contract()
    revised = contract.revised({"title": "변경", "contract_file_id": new_id()})
    assert (revised.id, revised.title) == (contract.id, "변경")

    with pytest.raises(BusinessRuleViolation) as exc:
        contract.revised({"end_date": date(2025, 1, 1)})
    assert exc.value.code == "invalid_contract_period"


@pytest.mark.parametrize(
    "status", [ContractStatus.ACTIVE, ContractStatus.ENDED, ContractStatus.TERMINATED]
)
def test_confirmed_contract_only_changes_manager(status: ContractStatus) -> None:
    contract = make_contract(contract_file_id=new_id(), status=status)
    manager = new_id()

    assert contract.revised({"manager_employee_id": manager}).manager_employee_id == manager
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.revised({"manager_employee_id": manager, "title": "변경"})
    assert exc.value.code == "contract_not_editable"


def test_confirm_requires_file() -> None:
    contract = make_contract()
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.confirm(today=TODAY)
    assert exc.value.code == "contract_file_required"


@pytest.mark.parametrize(
    ("end_date", "expected"),
    [
        (TODAY, ContractStatus.ACTIVE),  # 종료일 당일까지는 ACTIVE
        (date(2026, 11, 8), ContractStatus.ENDED),  # 이미 끝난 계약은 바로 ENDED
    ],
)
def test_confirm(end_date: date, expected: ContractStatus) -> None:
    contract = make_contract(contract_file_id=new_id(), end_date=end_date)
    contract.confirm(today=TODAY)
    assert contract.status is expected


def test_transitions() -> None:
    contract = make_contract(contract_file_id=new_id())
    with pytest.raises(BusinessRuleViolation):
        contract.terminate()  # DRAFT는 해지하지 않고 삭제한다

    contract.confirm(today=TODAY)
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.confirm(today=TODAY)
    assert exc.value.code == "invalid_contract_transition"

    contract.terminate()
    assert contract.status is ContractStatus.TERMINATED
    with pytest.raises(BusinessRuleViolation):
        contract.terminate()
    assert contract.expire(today=date(2030, 1, 1)) is False  # 해지된 계약은 만료 처리하지 않는다


def test_expire_after_end_date() -> None:
    contract = make_contract(contract_file_id=new_id(), end_date=TODAY)
    contract.confirm(today=TODAY)

    assert contract.expire(today=TODAY) is False
    assert contract.expire(today=date(2026, 11, 10)) is True
    assert contract.status is ContractStatus.ENDED
    assert contract.expire(today=date(2026, 11, 11)) is False


def test_only_draft_is_deletable() -> None:
    make_contract().ensure_deletable()
    contract = make_contract(contract_file_id=new_id(), status=ContractStatus.ACTIVE)
    with pytest.raises(BusinessRuleViolation) as exc:
        contract.ensure_deletable()
    assert exc.value.code == "contract_not_deletable"

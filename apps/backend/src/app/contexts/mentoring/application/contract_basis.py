"""기수 배정의 근거 계약 (decisions A110).

근거 계약 조건: 그 멘토의 멘토 계약, 상태 SIGNED·ACTIVE, 그 기수의 계약 또는 같은 과정의 과정 공통
계약(기수 없음), 배정 기간이 계약 기간 안. 멘토 계약은 항상 시간·회 단가라(A109⑩) 정산 조건은
계약에서 그대로 읽는다.
"""

import uuid
from typing import Protocol

from app.contexts.academy.domain.entities import Cohort
from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, ContractType, PriceUnit
from app.contexts.mentoring.domain.assignment import AssignmentTerms, CohortMentor
from app.contexts.mentoring.domain.enums import MentoringSettlementPolicy, PayUnit
from app.shared.errors import BusinessRuleViolation, NotFoundError

EFFECTIVE = frozenset({ContractStatus.SIGNED, ContractStatus.ACTIVE})
_PAY_UNITS = {PriceUnit.HOURLY: PayUnit.HOURLY, PriceUnit.PER_SESSION: PayUnit.PER_SESSION}


class ContractLookup(Protocol):
    """educator `MentorContractQueries`."""

    async def get(self, contract_id: uuid.UUID) -> EducatorContract | None: ...
    async def get_many(
        self, contract_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, EducatorContract]: ...
    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[EducatorContract]: ...


def fits_cohort(contract: EducatorContract, cohort: Cohort) -> bool:
    """그 기수의 계약이거나 같은 과정의 과정 공통 계약인지."""
    if contract.cohort_id is not None:
        return contract.cohort_id == cohort.id
    return contract.bootcamp_id == cohort.bootcamp_id


def is_candidate(contract: EducatorContract, mentor_id: uuid.UUID, cohort: Cohort) -> bool:
    """기간을 빼고 근거 계약이 될 수 있는지 (후보 목록)."""
    return (
        contract.contract_type is ContractType.MENTOR
        and contract.mentor_id == mentor_id
        and contract.status in EFFECTIVE
        and fits_cohort(contract, cohort)
    )


def ensure_basis(
    assignment: CohortMentor, contract: EducatorContract | None, cohort: Cohort
) -> EducatorContract:
    if contract is None:
        raise NotFoundError("근거 계약을 찾을 수 없습니다.", code="contract_not_found")
    if (
        contract.contract_type is not ContractType.MENTOR
        or contract.mentor_id != assignment.mentor_id
    ):
        raise BusinessRuleViolation(
            "이 멘토의 멘토 계약만 근거로 고를 수 있습니다.", code="assignment_contract_mismatch"
        )
    if contract.status not in EFFECTIVE:
        raise BusinessRuleViolation(
            "계약 완료·이행 중인 계약만 근거로 고를 수 있습니다.",
            code="assignment_contract_not_effective",
        )
    if not fits_cohort(contract, cohort):
        raise BusinessRuleViolation(
            "이 기수의 계약이나 같은 과정의 과정 공통 계약만 근거로 고를 수 있습니다.",
            code="assignment_contract_other_cohort",
        )
    assignment.ensure_within_contract(contract.start_date, contract.end_date)
    return contract


def terms_of(contract: EducatorContract) -> AssignmentTerms | None:
    """계약의 멘토링 정산 조건. 멘토 계약이 아니거나 칸이 비면 None."""
    unit = _PAY_UNITS.get(contract.price_unit) if contract.price_unit else None
    if (
        unit is None
        or contract.unit_price is None
        or contract.mentoring_time_basis is None
        or contract.no_show_pay_amount is None
    ):
        return None
    return AssignmentTerms(
        settlement_policy=MentoringSettlementPolicy(contract.mentoring_time_basis.value),
        pay_unit=unit,
        pay_rate=contract.unit_price,
        no_show_pay_amount=contract.no_show_pay_amount,
    )

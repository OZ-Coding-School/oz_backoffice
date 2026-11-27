"""educator 테스트 데이터 빌더. 멘토·강사 프로필은 가입 기능(P7) 전이라 직접 만든다."""

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.contexts.educator.domain.enums import (
    ContractType,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    VatType,
)
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.infrastructure.models import InstructorModel, MentorModel
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from tests.factories.identity import make_user

if TYPE_CHECKING:
    from app.contexts.identity.domain.enums import MemberSignupType
    from app.contexts.identity.domain.signup import MemberSignup


async def create_user(**overrides: Any) -> User:
    user = make_user(**overrides)
    await TortoiseUserRepository().add(user)
    return user


async def create_mentor(user: User | None = None, **overrides: Any) -> Mentor:
    user = user or await create_user()
    row = await MentorModel.create(user_id=user.id, **overrides)
    mentor = await TortoiseMentorRepository().get(row.id)
    assert mentor is not None
    return mentor


async def create_instructor(user: User | None = None) -> InstructorModel:
    user = user or await create_user()
    return await InstructorModel.create(user_id=user.id)


async def create_applicant_signup(
    signup_type: "MemberSignupType",
    *,
    cohort_id: "uuid.UUID | None" = None,
    **user_overrides: Any,
) -> tuple[User, "MemberSignup"]:
    """승인 대기 수강생·멘토(회원 PENDING + 가입 신청)."""
    from app.contexts.identity.domain.enums import member_account_type
    from app.contexts.identity.domain.signup import MemberSignup
    from app.contexts.identity.infrastructure.repositories import TortoiseMemberSignupRepository

    user_overrides.setdefault("account_type", member_account_type(signup_type))
    user = await create_user(**user_overrides)
    signup = MemberSignup(user_id=user.id, signup_type=signup_type, requested_cohort_id=cohort_id)
    await TortoiseMemberSignupRepository().add(signup)
    return user, signup


# 멘토 계약의 정산 조건 (A109⑩: 시간·회 단가 + 노쇼 금액 + 정산 시간 기준)
MENTOR_TERMS: dict[str, Any] = {
    "contract_type": ContractType.MENTOR,
    "settlement_type": SettlementType.UNIT_PRICE,
    "unit_price": 50000,
    "price_unit": PriceUnit.HOURLY,
    "no_show_pay_amount": 0,
    "mentoring_time_basis": MentoringTimeBasis.ACTUAL_DURATION,
    "vat_type": VatType.NOT_APPLICABLE,
}
# 강사 계약: 멘토 전용 칸을 비운다
INSTRUCTOR_TERMS: dict[str, Any] = {
    **MENTOR_TERMS,
    "contract_type": ContractType.INSTRUCTOR,
    "no_show_pay_amount": None,
    "mentoring_time_basis": None,
}


async def mentor_contract_fields(**overrides: Any) -> dict[str, Any]:
    """계약의 종류·과정·기수·금액 칸 (A109). 과정·기수를 새로 만든다."""
    from tests.factories.academy import create_cohort

    cohort = await create_cohort()
    return {
        **MENTOR_TERMS,
        "bootcamp_id": cohort.bootcamp_id,
        "cohort_id": cohort.id,
        **overrides,
    }


async def mentor_contract_json(**overrides: Any) -> dict[str, Any]:
    """API 요청 본문용 계약 칸 (UUID·enum을 문자열로)."""
    fields = await mentor_contract_fields(**overrides)
    return {k: (str(v) if isinstance(v, uuid.UUID | StrEnum) else v) for k, v in fields.items()}

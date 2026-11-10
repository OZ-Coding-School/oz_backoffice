"""가입 자동 매칭의 다른 컨텍스트 서비스 (실제 DB): 명단 연결, 멘토 계약 연결."""

import uuid
from datetime import date
from typing import Any

import pytest

from app.contexts.academy.application.student_claims import StudentClaims
from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.application.mentor_onboarding import MentorOnboarding
from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import (
    ContractStatus,
    DisplayNamePreference,
    EducatorType,
)
from app.contexts.educator.infrastructure.models import ContractFileModel
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseMentorRepository,
)
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user
from tests.factories.organization import create_employee

pytestmark = pytest.mark.integration

students = TortoiseStudentRepository()
NAME, PHONE = "김수강", "01055556666"


async def _student(cohort_id: uuid.UUID, **overrides: Any) -> Student:
    student = make_student(cohort_id=cohort_id, name=NAME, phone_number=PHONE, **overrides)
    await students.add(student)
    return student


async def test_claim_only_within_requested_cohort() -> None:
    requested, other = await create_cohort(), await create_cohort()
    await _student(other.id)  # 다른 기수 명단은 보지 않는다
    await _student(requested.id, status=EnrollmentStatus.COMPLETED)  # 수강 중 아님
    await _student(requested.id, is_removed_in_source=True)  # 원천에서 삭제
    target = await _student(requested.id)
    user = await create_user()

    outcome = await StudentClaims(students).claim_in_cohort(
        requested.id, name=NAME, phone_number=PHONE, user_id=user.id
    )

    assert (outcome.candidate_count, outcome.student_id) == (1, target.id)
    claimed = await students.get(target.id)
    assert claimed is not None
    assert claimed.user_id == user.id


async def test_no_claim_when_missing_or_duplicated() -> None:
    cohort = await create_cohort()
    user = await create_user()
    claims = StudentClaims(students)

    none = await claims.claim_in_cohort(cohort.id, name=NAME, phone_number=PHONE, user_id=user.id)
    await _student(cohort.id)
    await _student(cohort.id)
    duplicated = await claims.claim_in_cohort(
        cohort.id, name=NAME, phone_number=PHONE, user_id=user.id
    )

    assert (none.candidate_count, none.student_id) == (0, None)
    assert (duplicated.candidate_count, duplicated.student_id) == (2, None)


async def test_mentor_contracts_any_status_are_linked() -> None:
    contracts = TortoiseEducatorContractRepository()
    employee = await create_employee()

    async def contract(**overrides: Any) -> EducatorContract:
        values: dict[str, Any] = {
            "manager_employee_id": employee.id,
            "educator_type": EducatorType.MENTOR,
            "contractor_name": "김멘토",
            "contractor_phone": "01077778888",
            "title": "계약",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
        }
        values.update(overrides)
        if values.get("status", ContractStatus.DRAFT) is not ContractStatus.DRAFT:
            file = await ContractFileModel.create(
                file_name="a.pdf", file_ext="pdf", file_size=1, storage_key=f"contracts/{new_id()}"
            )
            values["contract_file_id"] = file.id
        entity = EducatorContract(**values)
        await contracts.add(entity)
        return entity

    draft = await contract()
    ended = await contract(status=ContractStatus.ENDED)
    await contract(educator_type=EducatorType.INSTRUCTOR)  # 강사 계약 제외
    other_mentor = await create_mentor()
    await contract(mentor_id=other_mentor.id)  # 이미 연결된 계약 제외
    user = await create_user(name="김멘토")

    match = await MentorOnboarding(
        contracts=contracts, mentors=TortoiseMentorRepository()
    ).link_contracts(
        user_id=user.id,
        name="김멘토",
        phone_number="01077778888",
        nickname="오즈",
        display_name_preference=DisplayNamePreference.NICKNAME,
    )

    assert sorted(match.contract_ids) == sorted([draft.id, ended.id])
    mentor = await TortoiseMentorRepository().get_by_user(user.id)
    assert mentor is not None
    assert (mentor.id, mentor.nickname) == (match.mentor_id, "오즈")
    for contract_id in (draft.id, ended.id):
        linked = await contracts.get(contract_id)
        assert linked is not None
        assert linked.mentor_id == mentor.id


async def test_selected_student_rules() -> None:
    from app.shared.errors import BusinessRuleViolation, NotFoundError

    cohort = await create_cohort()
    claims = StudentClaims(students)
    completed = await _student(cohort.id, status=EnrollmentStatus.COMPLETED)
    removed = await _student(cohort.id, is_removed_in_source=True)
    user = await create_user()

    # 수강 상태는 묻지 않는다 (A33)
    assert await claims.claim_selected(completed.id, user_id=user.id) == cohort.id
    for student_id, code in (
        (completed.id, "student_already_claimed"),
        (removed.id, "student_removed_in_source"),
    ):
        with pytest.raises(BusinessRuleViolation) as exc:
            await claims.cohort_of_claimable(student_id)
        assert exc.value.code == code
    with pytest.raises(NotFoundError):
        await claims.cohort_of_claimable(new_id())


async def test_mentor_approval_validates_selected_contracts() -> None:
    from app.shared.errors import BusinessRuleViolation, NotFoundError

    contracts = TortoiseEducatorContractRepository()
    employee = await create_employee()
    instructor_contract = EducatorContract(
        manager_employee_id=employee.id,
        educator_type=EducatorType.INSTRUCTOR,
        contractor_name="박강사",
        contractor_phone="01011112222",
        title="강의",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    await contracts.add(instructor_contract)
    onboarding = MentorOnboarding(contracts=contracts, mentors=TortoiseMentorRepository())
    user = await create_user()

    with pytest.raises(BusinessRuleViolation) as wrong:
        await onboarding.approve(
            user_id=user.id,
            nickname=None,
            display_name_preference=DisplayNamePreference.NAME,
            contract_ids=[instructor_contract.id],
        )
    assert wrong.value.code == "contract_not_linkable"
    with pytest.raises(NotFoundError):
        await onboarding.approve(
            user_id=user.id,
            nickname=None,
            display_name_preference=DisplayNamePreference.NAME,
            contract_ids=[new_id()],
        )

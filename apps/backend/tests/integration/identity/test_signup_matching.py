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
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.infrastructure.models import ContractFileModel
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseMentorRepository,
)
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_user
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


async def _mentor_contract(
    employee_id: uuid.UUID, mentor_id: uuid.UUID | None, **overrides: Any
) -> EducatorContract:
    values: dict[str, Any] = {
        "manager_employee_id": employee_id,
        "educator_type": EducatorType.MENTOR,
        "contractor_name": "김멘토",
        "contractor_phone": "01077778888",
        "title": "계약",
        "start_date": date(2026, 1, 1),
        "end_date": date(2099, 12, 31),
        "mentor_id": mentor_id,
    }
    values.update(overrides)
    if values.get("status", ContractStatus.DRAFT) is not ContractStatus.DRAFT:
        file = await ContractFileModel.create(
            file_name="a.pdf", file_ext="pdf", file_size=1, storage_key=f"contracts/{new_id()}"
        )
        values["contract_file_id"] = file.id
    entity = EducatorContract(**values)
    await TortoiseEducatorContractRepository().add(entity)
    return entity


async def test_signup_registers_the_pending_mentor() -> None:
    """가입 전 멘토(A104)가 하나면 계정을 연결한다. 진행 중 계약이 있으면 활성 (A105)."""
    mentors = TortoiseMentorRepository()
    employee = await create_employee()
    pending = Mentor.pending(name="김멘토", phone="01077778888")
    await mentors.add(pending)
    active = await _mentor_contract(employee.id, pending.id, status=ContractStatus.ACTIVE)
    draft = await _mentor_contract(employee.id, pending.id)
    # 예전 미연결 계약은 자동으로 잇지 않는다
    legacy = await _mentor_contract(employee.id, None)
    user = await create_user(name="김멘토")
    onboarding = MentorOnboarding(contracts=TortoiseEducatorContractRepository(), mentors=mentors)

    match = await onboarding.link_contracts(
        user_id=user.id,
        name="김멘토",
        phone_number="01077778888",
        nickname="오즈",
        display_name_preference=DisplayNamePreference.NICKNAME,
    )

    assert match.mentor_id == pending.id
    assert sorted(match.contract_ids) == sorted([active.id, draft.id])
    mentor = await mentors.get(pending.id)
    assert mentor is not None
    assert (mentor.user_id, mentor.nickname, mentor.is_active, mentor.contact_name) == (
        user.id,
        "오즈",
        True,
        None,
    )
    still = await TortoiseEducatorContractRepository().get(legacy.id)
    assert still is not None
    assert still.mentor_id is None


async def test_signup_without_active_contract_or_with_two_pending() -> None:
    mentors = TortoiseMentorRepository()
    employee = await create_employee()
    onboarding = MentorOnboarding(contracts=TortoiseEducatorContractRepository(), mentors=mentors)
    draft_only = Mentor.pending(name="이멘토", phone="01011112222")
    await mentors.add(draft_only)
    await _mentor_contract(employee.id, draft_only.id, contractor_name="이멘토")
    user = await create_user(name="이멘토")
    match = await onboarding.link_contracts(
        user_id=user.id,
        name="이멘토",
        phone_number="01011112222",
        nickname=None,
        display_name_preference=DisplayNamePreference.NAME,
    )
    registered = await mentors.get(draft_only.id)
    assert registered is not None
    assert (match.mentor_id, registered.is_active) == (draft_only.id, False)

    for _ in range(2):
        await mentors.add(Mentor.pending(name="박멘토", phone="01033334444"))
    other = await create_user(name="박멘토")
    twice = await onboarding.link_contracts(
        user_id=other.id,
        name="박멘토",
        phone_number="01033334444",
        nickname=None,
        display_name_preference=DisplayNamePreference.NAME,
    )
    assert (twice.mentor_id, twice.candidate_count) == (None, 2)
    nobody = await onboarding.link_contracts(
        user_id=other.id,
        name="없는사람",
        phone_number="01000000000",
        nickname=None,
        display_name_preference=DisplayNamePreference.NAME,
    )
    assert (nobody.mentor_id, nobody.candidate_count) == (None, 0)


async def test_manual_approval_with_pending_mentor() -> None:
    """운영진 승인 (A105): 가입 전 멘토를 고르면 그 멘토에 계정을 연결하고 예전 계약도 잇는다."""
    from app.shared.errors import BusinessRuleViolation

    mentors = TortoiseMentorRepository()
    employee = await create_employee()
    onboarding = MentorOnboarding(contracts=TortoiseEducatorContractRepository(), mentors=mentors)
    pending = Mentor.pending(name="최멘토", phone="01055550000")
    await mentors.add(pending)
    own = await _mentor_contract(employee.id, pending.id, contractor_name="최멘토")
    legacy = await _mentor_contract(employee.id, None, contractor_name="최멘토")
    candidates = await onboarding.candidate_mentors(
        name="최멘토", phone_number=None, query=None, limit=20
    )
    assert [(c.mentor_id, c.contract_count) for c in candidates] == [(pending.id, 1)]

    user = await create_user(name="최멘토2")
    match = await onboarding.approve(
        user_id=user.id,
        nickname=None,
        display_name_preference=DisplayNamePreference.NAME,
        contract_ids=[legacy.id],
        mentor_id=pending.id,
    )
    assert match.mentor_id == pending.id
    assert sorted(match.contract_ids) == sorted([own.id, legacy.id])
    with pytest.raises(BusinessRuleViolation) as again:
        await onboarding.approve(
            user_id=(await create_user()).id,
            nickname=None,
            display_name_preference=DisplayNamePreference.NAME,
            contract_ids=[],
            mentor_id=pending.id,
        )
    assert again.value.code == "mentor_already_registered"


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

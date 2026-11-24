"""수강생·멘토 가입 승인 관리 API (실제 DB, 메모리 디스패처)."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType, MemberSignupType
from app.contexts.identity.infrastructure.models import UserModel
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.access import ASSISTANT, give_role
from tests.factories.educator import create_applicant_signup
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

API = "/api/v1/admin/approvals"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _assistant(settings: Settings, cohort_id: object) -> dict[str, str]:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await give_role(user.id, ASSISTANT, cohort_id=cohort_id)  # type: ignore[arg-type]
    return bearer(settings, user)


async def test_admin_approves_student_with_roster_from_other_cohort(
    app: FastAPI, client: AsyncClient, admin: dict[str, str]
) -> None:
    requested, actual = await create_cohort(), await create_cohort()
    user, _ = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=requested.id)
    student = make_student(cohort_id=actual.id)  # 이름·휴대폰이 달라도 운영진 판단으로 연결
    await TortoiseStudentRepository().add(student)

    listed = await client.get(API, headers=admin)
    assert [item["user_id"] for item in listed.json()["items"]] == [str(user.id)]

    approved = await client.post(
        f"{API}/{user.id}/approve", json={"student_id": str(student.id)}, headers=admin
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["approval_status"] == "APPROVED"
    assert approved.json()["signup"]["status"] == "APPROVED"
    claimed = await TortoiseStudentRepository().get(student.id)
    assert claimed is not None
    assert claimed.user_id == user.id
    assert app.state.mail_dispatcher.dispatched[-1].subject.endswith("가입이 승인되었습니다")
    assert (await client.get(API, headers=admin)).json()["total"] == 0


async def test_assistant_sees_and_handles_only_own_cohort(
    client: AsyncClient, settings: Settings
) -> None:
    mine, other = await create_cohort(), await create_cohort()
    own_user, _ = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=mine.id)
    other_user, _ = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=other.id)
    mentor_user, _ = await create_applicant_signup(MemberSignupType.MENTOR)
    outside = make_student(cohort_id=other.id)
    await TortoiseStudentRepository().add(outside)
    assistant = await _assistant(settings, mine.id)

    listed = await client.get(API, headers=assistant)
    assert [item["user_id"] for item in listed.json()["items"]] == [str(own_user.id)]

    other_cohort = await client.post(
        f"{API}/{other_user.id}/reject", json={"reason": "x"}, headers=assistant
    )
    assert other_cohort.status_code == 403
    mentor = await client.post(f"{API}/{mentor_user.id}/approve", json={}, headers=assistant)
    assert mentor.status_code == 403  # 멘토 승인은 contract.manage
    out_of_scope = await client.post(
        f"{API}/{own_user.id}/approve", json={"student_id": str(outside.id)}, headers=assistant
    )
    assert out_of_scope.status_code == 403  # 고른 명단의 기수도 담당이어야 한다


async def test_mentor_approval_without_contract_creates_profile(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    user, _ = await create_applicant_signup(MemberSignupType.MENTOR)

    approved = await client.post(f"{API}/{user.id}/approve", json={}, headers=admin)

    assert approved.status_code == 200, approved.text
    assert await TortoiseMentorRepository().get_by_user(user.id) is not None
    wrong_type = await client.post(
        f"{API}/{user.id}/approve", json={"student_id": str(user.id)}, headers=admin
    )
    assert wrong_type.status_code == 404  # 대기 신청이 없다


async def test_reject_then_resubmit(
    app: FastAPI, client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    cohort = await create_cohort()
    user, _ = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=cohort.id)
    member = bearer(settings, user)

    rejected = await client.post(
        f"{API}/{user.id}/reject", json={"reason": "명단에 없습니다 <확인>"}, headers=admin
    )
    assert rejected.status_code == 200, rejected.text
    assert (await UserModel.get(id=user.id)).approval_status == "REJECTED"
    mail = app.state.mail_dispatcher.dispatched[-1]
    assert "명단에 없습니다 <확인>" in mail.text
    assert "&lt;확인&gt;" in mail.html

    mine = await client.get("/api/v1/me/member-signup", headers=member)
    assert (mine.json()["status"], mine.json()["reject_reason"]) == (
        "REJECTED",
        "명단에 없습니다 <확인>",
    )

    again = await client.post(
        "/api/v1/me/member-signup",
        json={"signup_type": "STUDENT", "cohort_id": str(cohort.id)},
        headers=member,
    )
    assert again.status_code == 201, again.text
    assert again.json()["approval_status"] == "PENDING"
    assert again.json()["signup"]["match_result"] == "NO_MATCH"
    assert (await UserModel.get(id=user.id)).account_type == "STUDENT"
    twice = await client.post(
        "/api/v1/me/member-signup",
        json={"signup_type": "STUDENT", "cohort_id": str(cohort.id)},
        headers=member,
    )
    assert twice.json()["error"]["code"] == "signup_not_rejected"

    # 승인 전이면 다른 유형으로 다시 신청할 때 계정 종류도 바뀐다 (A65)
    await client.post(f"{API}/{user.id}/reject", json={"reason": "멘토로"}, headers=admin)
    as_mentor = await client.post(
        "/api/v1/me/member-signup",
        json={"signup_type": "MENTOR", "nickname": "오즈"},
        headers=member,
    )
    assert as_mentor.status_code == 201, as_mentor.text
    assert (await UserModel.get(id=user.id)).account_type == "MENTOR"
    me = await client.get("/api/v1/me", headers=member)
    assert me.json()["account_type"] == "MENTOR"


async def test_approval_rejects_account_type_mismatch(
    client: AsyncClient, admin: dict[str, str]
) -> None:
    """계정 종류와 신청 유형이 다르면 승인하지 않는다 (A65, 두 역할을 함께 갖지 않게)."""
    user, _ = await create_applicant_signup(
        MemberSignupType.MENTOR, account_type=AccountType.STUDENT
    )
    response = await client.post(f"{API}/{user.id}/approve", json={}, headers=admin)
    assert (response.status_code, response.json()["error"]["code"]) == (
        422,
        "signup_type_mismatch",
    )


async def test_requires_user_approve(client: AsyncClient, settings: Settings) -> None:
    assert (await client.get(API)).status_code == 401
    plain = await create_applicant()
    plain.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(plain)
    assert (await client.get(API, headers=bearer(settings, plain))).status_code == 403


async def test_candidates_for_student_rank_matches_within_scope(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    """수동 승인 후보 (A82): 담당 범위의 미가입 명단, 일치 많은 순·신청 기수 먼저."""
    requested, other, outside = await create_cohort(), await create_cohort(), await create_cohort()
    user, _ = await create_applicant_signup(
        MemberSignupType.STUDENT, cohort_id=requested.id, name="가수강", phone_number="01012341234"
    )
    students = TortoiseStudentRepository()
    both = make_student(cohort_id=other.id, name="가수강", phone_number="01012341234")
    name_only = make_student(cohort_id=requested.id, name="가수강", phone_number="01099990000")
    phone_only = make_student(cohort_id=requested.id, name="가수현", phone_number="01012341234")
    far = make_student(cohort_id=outside.id, name="가수강")
    unrelated = make_student(cohort_id=requested.id, name="나수강")
    for s in (both, name_only, phone_only, far, unrelated):
        await students.add(s)

    res = await client.get(f"{API}/{user.id}/candidates", headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["signup_type"] == "STUDENT"
    assert body["contracts"] == []
    ids = [c["student_id"] for c in body["students"]]
    assert ids[0] == str(both.id)
    assert set(ids) == {str(both.id), str(name_only.id), str(phone_only.id), str(far.id)}
    first = body["students"][0]
    assert (first["name_match"], first["phone_match"], first["same_cohort"]) == (True, True, False)
    assert first["cohort_number"] == other.cohort_number
    assert first["bootcamp_name"]

    searched = await client.get(f"{API}/{user.id}/candidates", params={"q": "나수"}, headers=admin)
    assert [c["student_id"] for c in searched.json()["students"]] == [str(unrelated.id)]

    # 조교는 자기 기수 명단만
    assistant = await _assistant(settings, requested.id)
    scoped = await client.get(f"{API}/{user.id}/candidates", headers=assistant)
    assert {c["student_id"] for c in scoped.json()["students"]} == {
        str(name_only.id),
        str(phone_only.id),
    }
    listed = (await client.get(API, headers=admin)).json()["items"][0]
    assert listed["requested_bootcamp_name"]
    assert listed["requested_cohort_number"] == requested.cohort_number


async def test_candidates_for_mentor_are_unlinked_mentor_contracts(
    client: AsyncClient, settings: Settings, admin: dict[str, str]
) -> None:
    from datetime import date

    from app.contexts.educator.domain.entities import EducatorContract
    from app.contexts.educator.domain.enums import EducatorType
    from app.contexts.educator.infrastructure.repositories import TortoiseEducatorContractRepository
    from tests.factories.educator import create_mentor
    from tests.factories.organization import create_employee

    employee = await create_employee()
    contracts = TortoiseEducatorContractRepository()

    async def contract(**overrides: object) -> EducatorContract:
        values: dict[str, object] = {
            "manager_employee_id": employee.id,
            "educator_type": EducatorType.MENTOR,
            "contractor_name": "김멘토",
            "contractor_phone": "01077778888",
            "title": "멘토 계약",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
        }
        values.update(overrides)
        entity = EducatorContract(**values)  # type: ignore[arg-type]
        await contracts.add(entity)
        return entity

    user, _ = await create_applicant_signup(
        MemberSignupType.MENTOR, name="김멘토", phone_number="01077778888"
    )
    match = await contract()
    phone = await contract(contractor_name="김멘투")
    await contract(educator_type=EducatorType.INSTRUCTOR)  # 강사 계약 제외
    await contract(mentor_id=(await create_mentor()).id)  # 이미 연결 제외
    other = await contract(contractor_name="이멘토", contractor_phone="01011112222")

    body = (await client.get(f"{API}/{user.id}/candidates", headers=admin)).json()
    assert body["signup_type"] == "MENTOR"
    assert [c["contract_id"] for c in body["contracts"]] == [str(match.id), str(phone.id)]
    assert (body["contracts"][1]["name_match"], body["contracts"][1]["phone_match"]) == (
        False,
        True,
    )
    searched = await client.get(f"{API}/{user.id}/candidates", params={"q": "이멘"}, headers=admin)
    assert [c["contract_id"] for c in searched.json()["contracts"]] == [str(other.id)]

    assistant = await _assistant(settings, (await create_cohort()).id)
    assert (await client.get(f"{API}/{user.id}/candidates", headers=assistant)).status_code == 403

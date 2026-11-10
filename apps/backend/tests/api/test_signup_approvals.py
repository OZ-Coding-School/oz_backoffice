"""수강생·멘토 가입 승인 관리 API (실제 DB, 메모리 디스패처)."""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.models import UserRoleModel
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import MemberSignupType
from app.contexts.identity.infrastructure.models import UserModel
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_applicant_signup
from tests.factories.staff_review import create_applicant, seed_roles

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
    await seed_roles()
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        user.id,
        COHORT_ASSISTANT,
        RoleScopeType.COHORT,
        cohort_id,  # type: ignore[arg-type]
    )
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
    roles = await UserRoleModel.filter(user_id=user.id).prefetch_related("role")
    assert [(r.role.code, str(r.scope_id)) for r in roles] == [("STUDENT", str(actual.id))]
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
    twice = await client.post(
        "/api/v1/me/member-signup",
        json={"signup_type": "STUDENT", "cohort_id": str(cohort.id)},
        headers=member,
    )
    assert twice.json()["error"]["code"] == "signup_not_rejected"


async def test_requires_user_approve(client: AsyncClient, settings: Settings) -> None:
    assert (await client.get(API)).status_code == 401
    plain = await create_applicant()
    plain.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(plain)
    assert (await client.get(API, headers=bearer(settings, plain))).status_code == 403

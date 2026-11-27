"""기수 요약 API (decisions A96): 수강생 상태별 인원·배정 멘토·담당자 (실제 DB)."""

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.access import assign, give_permissions
from tests.factories.educator import create_mentor, create_mentor_contract, create_user
from tests.factories.organization import create_employee

pytestmark = pytest.mark.api


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def test_summary_counts_mentors_and_staff(client: AsyncClient, settings: Settings) -> None:
    cohort, other = await create_cohort(cohort_number=12), await create_cohort()
    students = TortoiseStudentRepository()
    member = await create_user(name="김가입")
    await students.add(make_student(cohort_id=cohort.id, user_id=member.id))
    await students.add(make_student(cohort_id=cohort.id, status=EnrollmentStatus.DROPPED))
    await students.add(make_student(cohort_id=cohort.id, is_removed_in_source=True))
    await students.add(make_student(cohort_id=other.id))

    mentor = await create_mentor(await create_user(name="이멘토", account_type=AccountType.MENTOR))
    contract = await create_mentor_contract(
        mentor.id, bootcamp_id=cohort.bootcamp_id, cohort_id=cohort.id
    )
    await TortoiseCohortMentorRepository().add(
        CohortMentor(
            cohort_id=cohort.id,
            mentor_id=mentor.id,
            contract_id=contract.id,
            start_date=date(2026, 11, 2),
        )
    )
    reader = await create_user(name="박매니저", account_type=AccountType.STAFF)
    reader.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(reader)
    await give_permissions(reader.id, {"academy.cohort.read"}, cohort_ids=(cohort.id,))
    course_owner = await create_employee(await create_user(name="최팀장"))
    await assign(course_owner, bootcamp_ids=(cohort.bootcamp_id,))

    response = await client.get(
        f"/api/v1/admin/cohorts/{cohort.id}/summary", headers=bearer(settings, reader)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["students"]["total"] == 2  # 원본에서 빠진 행 제외
    assert body["students"]["linked"] == 1
    assert body["students"]["by_status"]["ENROLLED"] == 1
    assert body["students"]["by_status"]["DROPPED"] == 1
    assert body["students"]["by_status"]["COMPLETED"] == 0
    assert [(m["name"], m["start_date"]) for m in body["mentors"]] == [("이멘토", "2026-11-02")]
    assert [(s["name"], s["scope"]) for s in body["staff"]] == [
        ("박매니저", "COHORT"),
        ("최팀장", "COURSE"),
    ]
    assert all(s["position_name"] for s in body["staff"])

    # 담당이 아닌 기수는 403
    forbidden = await client.get(
        f"/api/v1/admin/cohorts/{other.id}/summary", headers=bearer(settings, reader)
    )
    assert forbidden.status_code == 403

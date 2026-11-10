"""승인 대기 목록 범위 필터 (실제 DB)."""

import pytest

from app.contexts.identity.domain.enums import MemberSignupType
from app.contexts.identity.domain.repositories import PendingSignupFilter, SignupVisibility
from app.contexts.identity.infrastructure.repositories import TortoiseMemberSignupRepository
from tests.factories.academy import create_cohort
from tests.factories.educator import create_applicant_signup

pytestmark = pytest.mark.integration

repo = TortoiseMemberSignupRepository()


async def test_list_pending_respects_visibility() -> None:
    mine, other = await create_cohort(), await create_cohort()
    _, in_mine = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=mine.id)
    _, in_other = await create_applicant_signup(MemberSignupType.STUDENT, cohort_id=other.id)
    _, mentor = await create_applicant_signup(MemberSignupType.MENTOR)

    async def ids(visibility: SignupVisibility, **kwargs: object) -> list[object]:
        page, _ = await repo.list_pending(
            PendingSignupFilter(visibility=visibility, **kwargs),  # type: ignore[arg-type]
            limit=20,
            offset=0,
        )
        return [s.id for s in page]

    assert await ids(SignupVisibility()) == []
    assert await ids(SignupVisibility(student_cohort_ids=frozenset({mine.id}))) == [in_mine.id]
    assert await ids(SignupVisibility(student_bootcamp_ids=frozenset({other.bootcamp_id}))) == [
        in_other.id
    ]
    assert await ids(SignupVisibility(mentors=True)) == [mentor.id]
    everything = SignupVisibility(all_students=True, mentors=True)
    assert await ids(everything) == [in_mine.id, in_other.id, mentor.id]  # 오래된 순
    assert await ids(everything, signup_type=MemberSignupType.MENTOR) == [mentor.id]
    assert await ids(everything, cohort_id=other.id) == [in_other.id]


async def test_get_pending_by_user() -> None:
    user, signup = await create_applicant_signup(MemberSignupType.MENTOR)
    found = await repo.get_pending_by_user(user.id)
    assert found is not None
    assert found.id == signup.id

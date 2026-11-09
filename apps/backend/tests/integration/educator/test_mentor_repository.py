from datetime import date

import pytest

from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import EducatorType
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseInstructorRepository,
    TortoiseMentorRepository,
)
from app.shared.ids import new_id
from tests.factories.educator import create_instructor, create_mentor, create_user
from tests.factories.organization import create_employee

pytestmark = pytest.mark.integration

mentors = TortoiseMentorRepository()


async def test_search_by_user_fields_and_nickname() -> None:
    kim = await create_mentor(
        await create_user(name="김멘토", email="kim@mentor.com", phone_number="01011112222")
    )
    park = await create_mentor(
        await create_user(name="박강사", email="park@example.com", phone_number="01033334444"),
        nickname="오즈",
        is_active=False,
    )

    async def ids(query: str | None = None, is_active: bool | None = None) -> list[object]:
        page, _ = await mentors.list_page(query=query, is_active=is_active, limit=20, offset=0)
        return [m.id for m in page]

    assert await ids() == [park.id, kim.id]
    assert await ids("김멘") == [kim.id]
    assert await ids("MENTOR.com") == [kim.id]  # 이메일 대소문자 무시
    assert await ids("3333-4444") == [park.id]  # 휴대폰 숫자
    assert await ids("오즈") == [park.id]  # 닉네임
    assert await ids(is_active=True) == [kim.id]


async def test_round_trip_and_counts() -> None:
    mentor = await create_mentor(nickname="오즈")
    loaded = await mentors.get_by_user(mentor.user_id)
    assert loaded is not None
    assert (loaded.id, loaded.nickname, loaded.created_at is not None) == (mentor.id, "오즈", True)

    loaded.headline = "한 줄 소개"
    await mentors.save(loaded)
    saved = await mentors.get(mentor.id)
    assert saved is not None
    assert saved.headline == "한 줄 소개"

    contracts = TortoiseEducatorContractRepository()
    employee = await create_employee()
    for _ in range(2):
        await contracts.add(
            EducatorContract(
                manager_employee_id=employee.id,
                educator_type=EducatorType.MENTOR,
                contractor_name="김멘토",
                contractor_phone="01012345678",
                title="계약",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                mentor_id=mentor.id,
            )
        )
    assert await contracts.count_by_mentors([mentor.id, new_id()]) == {mentor.id: 2}
    assert await contracts.count_by_mentors([]) == {}

    instructor = await create_instructor()
    assert await TortoiseInstructorRepository().exists(instructor.id)
    assert not await TortoiseInstructorRepository().exists(new_id())

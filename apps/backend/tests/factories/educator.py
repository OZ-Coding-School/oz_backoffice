"""educator 테스트 데이터 빌더. 멘토·강사 프로필은 가입 기능(P7) 전이라 직접 만든다."""

from typing import Any

from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.infrastructure.models import InstructorModel, MentorModel
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from tests.factories.identity import make_user


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

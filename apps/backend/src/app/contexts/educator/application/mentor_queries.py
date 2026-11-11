"""멘토 조회·활성 상태 변경 (다른 컨텍스트용 공개 서비스, decisions A35·A36).

멘토링(기수 배정·멘토 활성화)이 쓴다. 트랜잭션은 호출하는 쪽이 연다.
"""

import uuid

from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import MentorRepository


class MentorQueries:
    def __init__(self, mentors: MentorRepository) -> None:
        self._mentors = mentors

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None:
        return await self._mentors.get(mentor_id)

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None:
        return await self._mentors.get_by_user(user_id)

    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]:
        return await self._mentors.get_many(mentor_ids)

    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None:
        """배정 생성·재활성화와 멘토 비활성화가 겹치지 않게 멘토 행을 잠근다."""
        return await self._mentors.lock(mentor_id)

    async def set_accepting(self, mentor: Mentor, on: bool) -> None:
        mentor.set_accepting(on)
        await self._mentors.save(mentor)

    async def set_active(self, mentor: Mentor, active: bool) -> None:
        if active:
            mentor.activate()
        else:
            mentor.deactivate()
        await self._mentors.save(mentor)

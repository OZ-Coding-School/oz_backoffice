"""가입한 멘토를 계약에 연결하고 멘토 프로필을 만든다 (decisions A6·A31).

다른 컨텍스트(가입)용 공개 서비스다.

이름 + 휴대폰이 같은 유형 MENTOR 계약 중 아직 멘토에 연결되지 않은 것을 찾는다(계약 상태 무관).
1건 이상이면 멘토 프로필(가입 때 고른 닉네임·표시 이름)을 만들고 그 계약을 모두 연결한다.
MENTOR 역할은 멘토 배정(P8)에서 부여한다(A17). 트랜잭션은 호출하는 쪽이 연다.
"""

import uuid
from dataclasses import dataclass

from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import EducatorContractRepository, MentorRepository


@dataclass(frozen=True, slots=True)
class MentorMatch:
    contract_ids: list[uuid.UUID]
    mentor_id: uuid.UUID | None  # 만든(또는 이미 있던) 멘토 프로필


class MentorOnboarding:
    def __init__(self, *, contracts: EducatorContractRepository, mentors: MentorRepository) -> None:
        self._contracts = contracts
        self._mentors = mentors

    async def link_contracts(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        phone_number: str,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
    ) -> MentorMatch:
        contracts = await self._contracts.find_unlinked_mentor_contracts(name, phone_number)
        if not contracts:
            return MentorMatch(contract_ids=[], mentor_id=None)
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            mentor = Mentor(
                user_id=user_id,
                nickname=nickname,
                display_name_preference=display_name_preference,
            )
            await self._mentors.add(mentor)
        for contract in contracts:
            contract.link(mentor_id=mentor.id, instructor_id=None)
            await self._contracts.save(contract)
        return MentorMatch(contract_ids=[c.id for c in contracts], mentor_id=mentor.id)

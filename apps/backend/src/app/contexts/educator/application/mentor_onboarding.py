"""가입한 멘토를 가입 전 멘토·계약에 연결한다 (decisions A6·A31·A105).

다른 컨텍스트(가입)용 공개 서비스다. 트랜잭션은 호출하는 쪽이 연다.

- 자동(A105): 연락처 이름 + 휴대폰이 같은 가입 전 멘토(A104)가 정확히 하나면 계정을 연결한다.
  가입 때 고른 닉네임·표시 이름을 넣고, 진행 중(ACTIVE) 계약이 있으면 활성으로 둔다.
  둘 이상이면 AMBIGUOUS, 없으면 NO_MATCH(운영진 승인 대기). 예전처럼 미연결 계약을 자동으로
  잇지는 않는다(기존 미연결 계약은 옮기지 않음, A104).
- 운영진 승인: 가입 전 멘토 하나(선택)와 예전 미연결 계약(0건 이상)을 고른다. 가입 전 멘토를
  고르지 않으면 새 멘토 프로필을 만든다(A33).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, DisplayNamePreference, EducatorType
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import (
    ContractFilter,
    EducatorContractRepository,
    MentorRepository,
)
from app.shared.errors import BusinessRuleViolation, NotFoundError


@dataclass(frozen=True, slots=True)
class MentorMatch:
    contract_ids: list[uuid.UUID]
    mentor_id: uuid.UUID | None  # 연결한(또는 만든) 멘토 프로필
    candidate_count: int = 0  # 자동 연결: 같은 사람인 가입 전 멘토 수 (2 이상이면 AMBIGUOUS)


@dataclass(frozen=True, slots=True)
class PendingMentorCandidate:
    """운영진 수동 승인 후보 가입 전 멘토 (A105)."""

    mentor_id: uuid.UUID
    name: str
    phone_number: str | None
    contract_count: int


@dataclass(frozen=True, slots=True)
class ContractCandidate:
    """운영진 수동 승인 후보 계약 (A82)."""

    contract_id: uuid.UUID
    contractor_name: str
    contractor_phone: str | None
    title: str
    status: str
    start_date: date
    end_date: date


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
        pending = await self._mentors.search_pending(
            name=name, phone=phone_number, query=None, limit=10
        )
        same = [m for m in pending if (m.contact_name, m.contact_phone) == (name, phone_number)]
        if len(same) != 1:
            return MentorMatch(contract_ids=[], mentor_id=None, candidate_count=len(same))
        mentor = await self._register(same[0], user_id, nickname, display_name_preference)
        return MentorMatch(
            contract_ids=await self._contract_ids(mentor.id), mentor_id=mentor.id, candidate_count=1
        )

    async def candidate_mentors(
        self, *, name: str, phone_number: str | None, query: str | None, limit: int
    ) -> list[PendingMentorCandidate]:
        """운영진 수동 승인 후보 (A105): 가입 전 멘토."""
        mentors = await self._mentors.search_pending(
            name=name, phone=phone_number, query=query, limit=limit
        )
        counts = await self._contracts.count_by_mentors([m.id for m in mentors])
        return [
            PendingMentorCandidate(
                mentor_id=m.id,
                name=m.contact_name or "",
                phone_number=m.contact_phone,
                contract_count=counts.get(m.id, 0),
            )
            for m in mentors
        ]

    async def candidate_contracts(
        self, *, name: str, phone_number: str | None, query: str | None, limit: int
    ) -> list[ContractCandidate]:
        """운영진 수동 승인 후보 (A82): 미연결 MENTOR 계약, 상태 무관 (A33)."""
        contracts = await self._contracts.search_unlinked_mentor_contracts(
            name=name, phone_number=phone_number, query=query, limit=limit
        )
        return [
            ContractCandidate(
                contract_id=c.id,
                contractor_name=c.contractor_name,
                contractor_phone=c.contractor_phone,
                title=c.title,
                status=str(c.status),
                start_date=c.start_date,
                end_date=c.end_date,
            )
            for c in contracts
        ]

    async def approve(
        self,
        *,
        user_id: uuid.UUID,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
        contract_ids: list[uuid.UUID],
        mentor_id: uuid.UUID | None = None,
    ) -> MentorMatch:
        """운영진 승인 (P7-5, A33·A105): 가입 전 멘토(선택)에 계정을 연결하고, 고른 예전 미연결
        계약(0건 이상)도 그 멘토에 잇는다. 가입 전 멘토를 고르지 않으면 새 멘토 프로필을 만든다.

        고른 계약은 유형 MENTOR이고 아직 멘토에 연결되지 않아야 한다(상태 무관).
        """
        registered: Mentor | None = None
        if mentor_id is not None:
            pending = await self._mentors.get(mentor_id)
            if pending is None:
                raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
            if pending.is_registered:
                raise BusinessRuleViolation(
                    "이미 가입한 멘토입니다.", code="mentor_already_registered"
                )
            registered = await self._register(pending, user_id, nickname, display_name_preference)
        contracts = []
        for contract_id in dict.fromkeys(contract_ids):
            contract = await self._contracts.get(contract_id)
            if contract is None:
                raise NotFoundError("계약을 찾을 수 없습니다.", code="contract_not_found")
            if contract.educator_type is not EducatorType.MENTOR or contract.mentor_id is not None:
                raise BusinessRuleViolation(
                    "연결할 수 없는 계약입니다 (멘토 계약이 아니거나 이미 연결됨).",
                    code="contract_not_linkable",
                )
            contracts.append(contract)
        match = await self._onboard(user_id, nickname, display_name_preference, contracts)
        if registered is not None:
            return MentorMatch(
                contract_ids=await self._contract_ids(registered.id), mentor_id=registered.id
            )
        return match

    async def _register(
        self,
        pending: Mentor,
        user_id: uuid.UUID,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
    ) -> Mentor:
        """가입 전 멘토에 계정을 연결한다. 진행 중 계약이 있으면 활성으로 둔다 (A105)."""
        active, _ = await self._contracts.list_page(
            ContractFilter(statuses=frozenset({ContractStatus.ACTIVE}), mentor_id=pending.id),
            limit=1,
            offset=0,
        )
        mentor = pending.with_profile(
            {"nickname": nickname, "display_name_preference": display_name_preference}
        )
        mentor.register(user_id, activate=bool(active))
        await self._mentors.save(mentor)
        return mentor

    async def _contract_ids(self, mentor_id: uuid.UUID) -> list[uuid.UUID]:
        contracts, _ = await self._contracts.list_page(
            ContractFilter(mentor_id=mentor_id), limit=100, offset=0
        )
        return [c.id for c in contracts]

    async def _onboard(
        self,
        user_id: uuid.UUID,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
        contracts: list[EducatorContract],
    ) -> MentorMatch:
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

"""멘토 계약 조회 (다른 컨텍스트용 공개 서비스, decisions A110).

멘토링의 기수 배정이 근거 계약을 확인하고, 정산이 계약의 단가·노쇼 금액·정산 시간 기준을 읽는다.
트랜잭션은 호출하는 쪽이 연다.
"""

import uuid

from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.repositories import EducatorContractRepository


class MentorContractQueries:
    def __init__(self, contracts: EducatorContractRepository) -> None:
        self._contracts = contracts

    async def get(self, contract_id: uuid.UUID) -> EducatorContract | None:
        return await self._contracts.get(contract_id)

    async def get_many(self, contract_ids: list[uuid.UUID]) -> dict[uuid.UUID, EducatorContract]:
        return {c.id: c for c in await self._contracts.list_by_ids(list(set(contract_ids)))}

    async def list_by_mentor(self, mentor_id: uuid.UUID) -> list[EducatorContract]:
        return await self._contracts.list_mentor_contracts(mentor_id)

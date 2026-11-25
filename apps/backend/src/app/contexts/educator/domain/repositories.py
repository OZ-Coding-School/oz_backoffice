import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.contexts.educator.domain.profiles import Mentor


@dataclass(frozen=True, slots=True)
class ContractFilter:
    statuses: frozenset[ContractStatus] = frozenset()
    educator_type: EducatorType | None = None
    # 계약자 이름·제목 부분 일치, 숫자가 있으면 휴대폰 부분 일치
    query: str | None = None
    # 연결된 멘토 프로필 (A103)
    mentor_id: uuid.UUID | None = None


class EducatorContractRepository(Protocol):
    async def add(self, contract: EducatorContract) -> None: ...
    async def save(self, contract: EducatorContract) -> None: ...
    async def delete(self, contract_id: uuid.UUID) -> None: ...
    async def get(self, contract_id: uuid.UUID) -> EducatorContract | None: ...
    async def get_by_file(self, file_id: uuid.UUID) -> EducatorContract | None: ...
    async def list_page(
        self, contract_filter: ContractFilter, *, limit: int, offset: int
    ) -> tuple[list[EducatorContract], int]: ...
    async def list_active_ended_before(self, today: date) -> list[EducatorContract]: ...
    async def count_by_mentors(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]: ...
    async def search_unlinked_mentor_contracts(
        self, *, name: str, phone_number: str | None, query: str | None, limit: int
    ) -> list[EducatorContract]:
        """멘토에 연결되지 않은 MENTOR 계약 (상태 무관).
        query가 없으면 이름 또는 휴대폰이 같은 것."""
        ...

    async def find_unlinked_mentor_contracts(
        self, contractor_name: str, contractor_phone: str
    ) -> list[EducatorContract]:
        """가입 자동 매칭 후보: 유형 MENTOR, 아직 멘토에 연결되지 않은 계약 (상태 무관, A31)."""
        ...


class ContractFileRepository(Protocol):
    async def add(self, file: ContractFile) -> None: ...
    async def save(self, file: ContractFile) -> None: ...
    async def get(self, file_id: uuid.UUID) -> ContractFile | None: ...
    async def list_by_ids(self, file_ids: list[uuid.UUID]) -> list[ContractFile]: ...


class MentorRepository(Protocol):
    async def add(self, mentor: Mentor) -> None: ...
    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...
    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...
    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]: ...
    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None:
        """행을 잠그고 읽는다 (SELECT … FOR UPDATE, 트랜잭션 안에서)."""
        ...

    async def save(self, mentor: Mentor) -> None: ...
    async def delete(self, mentor_id: uuid.UUID) -> None: ...
    async def find_same_person(self, name: str, phone: str) -> list[Mentor]:
        """이름·휴대폰이 같은 멘토: 가입한 멘토는 회원 정보, 가입 전 멘토는 연락처로 (A104)."""
        ...

    async def list_page(
        self,
        *,
        query: str | None,
        is_active: bool | None,
        limit: int,
        offset: int,
        registered: bool | None = None,
    ) -> tuple[list[Mentor], int]:
        """query: 회원 이름·이메일·휴대폰(숫자)·닉네임, 가입 전 연락처 부분 일치.
        registered: True면 가입한 멘토, False면 가입 전 멘토만 (A104)."""
        ...


class InstructorRepository(Protocol):
    async def exists(self, instructor_id: uuid.UUID) -> bool: ...

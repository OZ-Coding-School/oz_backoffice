import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.contexts.educator.domain.entities import (
    ContractAmendment,
    ContractFile,
    EducatorContract,
)
from app.contexts.educator.domain.enums import ContractStatus, ContractType
from app.contexts.educator.domain.profiles import Mentor


@dataclass(frozen=True, slots=True)
class ContractFilter:
    statuses: frozenset[ContractStatus] = frozenset()
    contract_types: frozenset[ContractType] = frozenset()
    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None
    # 계약자 이름·제목 부분 일치, 숫자가 있으면 휴대폰 부분 일치
    query: str | None = None
    # 연결된 멘토 프로필 (A103)
    mentor_id: uuid.UUID | None = None
    # 담당 범위 (A109⑦): None이면 전부, 아니면 이 과정의 계약이나 이 기수의 계약만
    visible: "ContractVisibility | None" = None
    # 기수 필터와 함께 쓰면 이 과정의 과정 공통 계약(cohort_id NULL)도 함께 (A112).
    # 서비스가 기수의 과정을 찾아 채운다.
    common_bootcamp_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ContractVisibility:
    bootcamp_ids: frozenset[uuid.UUID] = frozenset()
    cohort_ids: frozenset[uuid.UUID] = frozenset()

    def allows(self, contract: EducatorContract) -> bool:
        return contract.bootcamp_id in self.bootcamp_ids or (
            contract.cohort_id is not None and contract.cohort_id in self.cohort_ids
        )


class EducatorContractRepository(Protocol):
    async def add(self, contract: EducatorContract) -> None: ...
    async def save(self, contract: EducatorContract) -> None: ...
    async def delete(self, contract_id: uuid.UUID) -> None: ...
    async def get(self, contract_id: uuid.UUID) -> EducatorContract | None: ...
    async def get_by_file(self, file_id: uuid.UUID) -> EducatorContract | None: ...
    async def list_page(
        self, contract_filter: ContractFilter, *, limit: int, offset: int
    ) -> tuple[list[EducatorContract], int]: ...
    async def count_by_types(self, contract_filter: ContractFilter) -> dict[ContractType, int]:
        """종류 필터만 빼고 같은 조건의 종류별 건수 (A112)."""
        ...

    async def list_by_ids(self, contract_ids: list[uuid.UUID]) -> list[EducatorContract]: ...
    async def list_mentor_contracts(self, mentor_id: uuid.UUID) -> list[EducatorContract]:
        """그 멘토의 멘토 계약 전체 (최근 것부터, 배정의 근거 계약 후보 A110)."""
        ...

    async def list_due(self, today: date) -> list[EducatorContract]:
        """날짜로 넘길 계약: 시작일이 된 SIGNED, 종료일이 지난 ACTIVE (매일 작업)."""
        ...

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


class ContractAmendmentRepository(Protocol):
    async def add(self, amendment: ContractAmendment) -> None: ...
    async def list_by_contract(self, contract_id: uuid.UUID) -> list[ContractAmendment]:
        """최근 변경이 먼저"""
        ...

    async def file_in_use(self, file_id: uuid.UUID) -> bool: ...


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

    async def search_pending(
        self, *, name: str, phone: str | None, query: str | None, limit: int
    ) -> list[Mentor]:
        """가입 전 멘토 (A105). query가 없으면 이름 또는 휴대폰이 같은 멘토,
        있으면 연락처 이름 부분 일치·휴대폰 숫자 부분 일치."""
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

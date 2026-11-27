"""계약 화면의 사람·과정 이름 (decisions A103·A109).

계약 응답의 담당 직원 이름·연결된 프로필 이름과 담당 직원 후보는 조직·회원 정보가
필요해 composition(`app/composition/contract_people.py`)이 모으고, presentation이
`app.state.contract_people`에서 꺼내 쓴다(decisions B10).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.contexts.educator.domain.entities import EducatorContract


@dataclass(frozen=True, slots=True)
class LinkedPerson:
    """연결된 멘토·강사: 실명과 수강생에게 보이는 이름"""

    name: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ContractPeople:
    managers: dict[uuid.UUID, str] = field(default_factory=dict)
    mentors: dict[uuid.UUID, LinkedPerson] = field(default_factory=dict)
    instructors: dict[uuid.UUID, LinkedPerson] = field(default_factory=dict)
    # 과정 이름, 기수 번호 (A109②)
    bootcamps: dict[uuid.UUID, str] = field(default_factory=dict)
    cohorts: dict[uuid.UUID, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ManagerCandidate:
    employee_id: uuid.UUID
    name: str
    email: str
    department_name: str
    team_name: str | None
    position_name: str
    is_me: bool


class ContractPeopleReader(Protocol):
    async def people(self, contracts: Sequence[EducatorContract]) -> ContractPeople: ...

    async def user_names(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        """변경 계약 등록자 이름 (A109⑨)"""
        ...

    async def manager_candidates(
        self, *, query: str | None, limit: int, me: uuid.UUID
    ) -> list[ManagerCandidate]: ...

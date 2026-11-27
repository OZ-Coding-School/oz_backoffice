"""계약 화면의 사람·과정 이름 (decisions A103·A109).

담당 직원·연결된 멘토·강사 이름, 과정·기수 이름, 담당 직원 후보.

조직(직원·부서·팀·직위)과 회원(이름·이메일), 강사·멘토 프로필을 모은다.
"""

import uuid
from collections.abc import Sequence

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.educator.application.contract_people import (
    ContractPeople,
    LinkedPerson,
    ManagerCandidate,
)
from app.contexts.educator.domain.entities import EducatorContract
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.infrastructure.repositories import (
    TortoiseInstructorRepository,
    TortoiseMentorRepository,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.infrastructure.repositories import (
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)


def _person(mentor: Mentor, name: str | None) -> LinkedPerson:
    """가입 전 멘토(A104)는 연락처 이름"""
    real = name or ""
    return LinkedPerson(real, mentor.display_name(real))


class ContractPeopleComposer:
    async def people(self, contracts: Sequence[EducatorContract]) -> ContractPeople:
        employees = await TortoiseEmployeeRepository().list_by_ids(
            list({c.manager_employee_id for c in contracts})
        )
        mentors = await TortoiseMentorRepository().get_many(
            list({c.mentor_id for c in contracts if c.mentor_id})
        )
        instructors = await TortoiseInstructorRepository().user_ids(
            list({c.instructor_id for c in contracts if c.instructor_id})
        )
        user_ids = (
            {e.user_id for e in employees}
            | {m.user_id for m in mentors.values() if m.user_id}
            | set(instructors.values())
        )
        names = {u.id: u.name for u in await TortoiseUserRepository().list_by_ids(list(user_ids))}
        academy = AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository())
        labels = await academy.cohort_labels({c.cohort_id for c in contracts if c.cohort_id})
        return ContractPeople(
            bootcamps=await academy.bootcamp_names({c.bootcamp_id for c in contracts}),
            cohorts={cohort_id: label.cohort_number for cohort_id, label in labels.items()},
            managers={e.id: names[e.user_id] for e in employees if e.user_id in names},
            mentors={
                m.id: _person(m, names.get(m.user_id) if m.user_id else m.contact_name)
                for m in mentors.values()
            },
            instructors={
                i: LinkedPerson(names[u], names[u]) for i, u in instructors.items() if u in names
            },
        )

    async def user_names(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        users = await TortoiseUserRepository().list_by_ids(list(set(user_ids)))
        return {u.id: u.name for u in users}

    async def manager_candidates(
        self, *, query: str | None, limit: int, me: uuid.UUID
    ) -> list[ManagerCandidate]:
        """직원 이름·이메일 검색. 정확히 같은 이름 → 이름이 검색어로 시작 → 나머지, 이름순.
        검색어가 없으면 나를 맨 앞에 둔다."""
        employees = await TortoiseEmployeeRepository().search(query=query)
        users = {
            u.id: u
            for u in await TortoiseUserRepository().list_by_ids([e.user_id for e in employees])
        }
        departments = {d.id: d.name for d in await TortoiseDepartmentRepository().list_all()}
        teams = {t.id: t.name for t in await TortoiseTeamRepository().list_all()}
        positions = {p.id: p.name for p in await TortoiseEmployeePositionRepository().list_all()}
        term = (query or "").strip()

        def rank(name: str, user_id: uuid.UUID) -> tuple[int, str]:
            if not term:
                return (0 if user_id == me else 1, name)
            if name == term:
                return (0, name)
            return (1 if name.startswith(term) else 2, name)

        found = [(e, users[e.user_id]) for e in employees if e.user_id in users]
        found.sort(key=lambda pair: rank(pair[1].name, pair[1].id))
        return [
            ManagerCandidate(
                employee_id=e.id,
                name=u.name,
                email=u.email,
                department_name=departments.get(e.department_id, "—"),
                team_name=teams.get(e.team_id) if e.team_id else None,
                position_name=positions.get(e.position_id, "—"),
                is_me=u.id == me,
            )
            for e, u in found[:limit]
        ]

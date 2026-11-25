"""회원 상세의 계정 종류별 연결 정보 (decisions A94).

수강생은 학사(수강 기수), 멘토는 강사·멘토링(배정 기수·계약 수),
운영진은 조직(소속·직위)에서 모은다.
"""

import uuid
from datetime import date

from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseMentorRepository,
)
from app.contexts.identity.application.member_admin import (
    MemberAssignment,
    MemberEnrollment,
    MemberLinks,
)
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.contexts.organization.infrastructure.repositories import (
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)


class MemberLinksComposer:
    async def links_of(self, user: User) -> MemberLinks:
        if user.account_type is AccountType.STUDENT:
            return await self._student(user)
        if user.account_type is AccountType.MENTOR:
            return await self._mentor(user)
        return await self._staff(user)

    async def _cohort_names(
        self, cohort_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, int, date]]:
        cohorts = await TortoiseCohortRepository().list_by_ids(cohort_ids)
        bootcamps = {b.id: b.name for b in await TortoiseBootcampRepository().list_all()}
        return {
            c.id: (bootcamps.get(c.bootcamp_id, "—"), c.cohort_number, c.start_date)
            for c in cohorts
        }

    async def _student(self, user: User) -> MemberLinks:
        students = await TortoiseStudentRepository().list_by_user(user.id)
        names = await self._cohort_names({s.cohort_id for s in students})
        ordered = sorted(
            (s for s in students if s.cohort_id in names),
            key=lambda s: names[s.cohort_id][2],
            reverse=True,
        )
        return MemberLinks(
            enrollments=[
                MemberEnrollment(
                    bootcamp_name=names[s.cohort_id][0],
                    cohort_number=names[s.cohort_id][1],
                    status=s.status.value,
                )
                for s in ordered
            ]
        )

    async def _mentor(self, user: User) -> MemberLinks:
        mentor = await TortoiseMentorRepository().get_by_user(user.id)
        if mentor is None:
            return MemberLinks(contract_count=0)
        assignments = await TortoiseCohortMentorRepository().list_by_mentor(
            mentor.id, include_inactive=True
        )
        names = await self._cohort_names({a.cohort_id for a in assignments})
        counts = await TortoiseEducatorContractRepository().count_by_mentors([mentor.id])
        return MemberLinks(
            assignments=[
                MemberAssignment(
                    bootcamp_name=names[a.cohort_id][0],
                    cohort_number=names[a.cohort_id][1],
                    active=a.is_active,
                )
                for a in assignments
                if a.cohort_id in names
            ],
            contract_count=counts.get(mentor.id, 0),
        )

    async def _staff(self, user: User) -> MemberLinks:
        employee = await TortoiseEmployeeRepository().get_by_user(user.id)
        if employee is None:
            return MemberLinks()
        department = await TortoiseDepartmentRepository().get(employee.department_id)
        team = await TortoiseTeamRepository().get(employee.team_id) if employee.team_id else None
        position = await TortoiseEmployeePositionRepository().get(employee.position_id)
        return MemberLinks(
            department_name=department.name if department else None,
            team_name=team.name if team else None,
            position_name=position.name if position else None,
        )

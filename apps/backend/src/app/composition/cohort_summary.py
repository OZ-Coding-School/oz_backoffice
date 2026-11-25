"""기수 요약 조합 (decisions A96).

수강생 인원은 학사 명단, 배정 멘토는 멘토링 배정 + 강사·멘토 프로필 + 회원 이름,
담당자는 조직의 기수·과정 담당 배정 + 직원 + 직위 + 회원 이름에서 모은다.
"""

import uuid
from collections import Counter
from typing import Literal

from app.contexts.academy.application.cohort_summary import (
    CohortStudentCounts,
    CohortSummary,
    CohortSummaryMentor,
    CohortSummaryStaff,
)
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampStaffRepository,
    TortoiseCohortStaffRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
)


class CohortSummaryComposer:
    async def summary_of(self, cohort_id: uuid.UUID, bootcamp_id: uuid.UUID) -> CohortSummary:
        students = await TortoiseStudentRepository().list_by_cohort(
            cohort_id, claimed=None, include_removed=False
        )
        counts = Counter(s.status.value for s in students)
        assignments = await TortoiseCohortMentorRepository().list_by_cohort(
            cohort_id, include_inactive=False
        )
        mentors = await TortoiseMentorRepository().get_many([a.mentor_id for a in assignments])
        cohort_staff = await TortoiseCohortStaffRepository().list_by_cohort(cohort_id)
        course_staff = await TortoiseBootcampStaffRepository().list_by_bootcamp(bootcamp_id)
        employee_ids = {s.employee_id for s in cohort_staff} | {s.employee_id for s in course_staff}
        employees = {
            e.id: e for e in await TortoiseEmployeeRepository().list_by_ids(list(employee_ids))
        }
        positions = {p.id: p.name for p in await TortoiseEmployeePositionRepository().list_all()}
        user_ids = [m.user_id for m in mentors.values()] + [e.user_id for e in employees.values()]
        names = {u.id: u.name for u in await TortoiseUserRepository().list_by_ids(user_ids)}

        mentor_rows = [
            CohortSummaryMentor(
                mentor_id=a.mentor_id,
                name=names.get(mentors[a.mentor_id].user_id, "—"),
                start_date=a.start_date,
            )
            for a in assignments
            if a.mentor_id in mentors
        ]
        staff_rows: list[CohortSummaryStaff] = []
        scoped: list[tuple[Literal["COHORT", "COURSE"], uuid.UUID]] = [
            *(("COHORT", s.employee_id) for s in cohort_staff),
            *(("COURSE", s.employee_id) for s in course_staff),
        ]
        seen: set[uuid.UUID] = set()
        for scope, employee_id in scoped:
            employee = employees.get(employee_id)
            if employee is None or employee.id in seen:
                continue
            seen.add(employee.id)
            staff_rows.append(
                CohortSummaryStaff(
                    employee_id=employee.id,
                    name=names.get(employee.user_id, "—"),
                    position_name=positions.get(employee.position_id),
                    scope=scope,
                )
            )
        return CohortSummary(
            students=CohortStudentCounts(
                total=len(students),
                linked=sum(1 for s in students if s.user_id is not None),
                by_status={
                    status.value: counts.get(status.value, 0) for status in EnrollmentStatus
                },
            ),
            mentors=sorted(mentor_rows, key=lambda m: (m.start_date, m.name)),
            staff=sorted(staff_rows, key=lambda s: (s.scope != "COHORT", s.name)),
        )

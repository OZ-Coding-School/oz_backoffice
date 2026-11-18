"""내 수강 등록 목록 (decisions A64).

회원에게 연결된 수강 등록을 상태와 무관하게 모두 돌려준다(수강 중·수료·중도포기·조기취업).
과정·기수 정보를 함께 붙이고, 기수 시작일이 늦은 것부터 정렬한다.
"""

import uuid
from dataclasses import dataclass

from app.contexts.academy.domain.entities import Bootcamp, Cohort, Student
from app.contexts.academy.domain.repositories import (
    BootcampRepository,
    CohortRepository,
    StudentRepository,
)


@dataclass(frozen=True, slots=True)
class MyEnrollment:
    student: Student
    cohort: Cohort
    bootcamp: Bootcamp


class EnrollmentQueries:
    def __init__(
        self,
        *,
        students: StudentRepository,
        cohorts: CohortRepository,
        bootcamps: BootcampRepository,
    ) -> None:
        self._students = students
        self._cohorts = cohorts
        self._bootcamps = bootcamps

    async def of_user(self, user_id: uuid.UUID) -> list[MyEnrollment]:
        students = await self._students.list_by_user(user_id)
        if not students:
            return []
        cohorts = {
            c.id: c for c in await self._cohorts.list_by_ids({s.cohort_id for s in students})
        }
        bootcamps = {b.id: b for b in await self._bootcamps.list_all()}
        found = [
            MyEnrollment(student=s, cohort=cohort, bootcamp=bootcamps[cohort.bootcamp_id])
            for s in students
            if (cohort := cohorts.get(s.cohort_id)) is not None and cohort.bootcamp_id in bootcamps
        ]
        return sorted(found, key=lambda e: (e.cohort.start_date, e.cohort.id), reverse=True)

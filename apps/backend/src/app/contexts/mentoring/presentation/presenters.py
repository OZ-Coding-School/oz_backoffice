"""신청·세션 응답에 이름을 붙인다 (신청자·팀·멘토, 각각 IN 쿼리 한 번).

수강생·멘토 응답에는 멘토 표시 이름만, 운영진 응답에만 멘토 실명을 넣는다(A28 표시 이름).
"""

import uuid
from dataclasses import dataclass
from typing import cast

from fastapi import Request
from pydantic import BaseModel, Field

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.request_service import StudentLookup
from app.contexts.mentoring.domain.balance import request_balance
from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType, RequestBalanceState
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.infrastructure.repositories import TortoiseMentoringTeamRepository


class RequestBalanceResponse(BaseModel):
    state: RequestBalanceState = Field(
        description="HELD 차감 예정 · USED 차감됨 · RETURNED 돌려받음 · NONE (A66)"
    )
    minutes: int


def balance_response(
    entries: list[tuple[MentoringBalanceTransactionType, int]],
) -> RequestBalanceResponse:
    result = request_balance(entries)
    return RequestBalanceResponse(state=result.state, minutes=result.minutes)


class Participant(BaseModel):
    student_id: uuid.UUID = Field(description="수강 등록(students.id)")
    name: str


@dataclass(frozen=True, slots=True)
class Names:
    team_label: str | None
    requester_name: str
    mentor_display_name: str
    mentor_name: str
    mentor_headline: str | None
    requester_cohort_id: uuid.UUID | None = None
    requester_status: EnrollmentStatus | None = None


class NameBook:
    def __init__(self, request: Request) -> None:
        state = request.app.state
        self._students = cast("StudentLookup", state.student_queries)
        self._mentors = cast("MentorDirectory", state.mentor_queries)
        self._users = cast("UserQueries", state.user_queries)
        self._catalog = cast("AcademyCatalog", state.academy_catalog)
        self._teams = TortoiseMentoringTeamRepository()

    async def of(self, items: list[MentoringRequest]) -> dict[uuid.UUID, Names]:
        """신청 id → 이름."""
        students = await self._students.get_many(list({r.requester_id for r in items}))
        team_ids = list({r.team_id for r in items if r.team_id})
        teams = {t.id: t for t in await self._teams.list_by_ids(team_ids)}
        mentors = await self._mentors.get_many(list({r.mentor_id for r in items}))
        users = await self._users.get_many([m.account_id for m in mentors.values()])
        result: dict[uuid.UUID, Names] = {}
        for r in items:
            mentor = mentors.get(r.mentor_id)
            user = users.get(mentor.account_id) if mentor else None
            real = user.name if user else ""
            student = students.get(r.requester_id)
            team = teams.get(r.team_id) if r.team_id else None
            result[r.id] = Names(
                team_label=team.label if team else None,
                requester_name=student.name if student else "",
                mentor_display_name=mentor.display_name(real) if mentor else "",
                mentor_name=real,
                mentor_headline=mentor.headline if mentor else None,
                requester_cohort_id=student.cohort_id if student else None,
                requester_status=student.status if student else None,
            )
        return result

    async def cohort_labels(self, cohort_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[str, int]]:
        """기수 id → (과정명, 기수 번호) (A76). IN 쿼리 한 번."""
        labels = await self._catalog.cohort_labels(cohort_ids)
        return {k: (v.bootcamp_name, v.cohort_number) for k, v in labels.items()}

    async def participants(
        self, items: list[MentoringRequest]
    ) -> dict[uuid.UUID, list[Participant]]:
        """신청 id → 참여자: 1:1은 신청자, 팀은 지금 팀원 (A68). IN 쿼리 두 번."""
        teams = {
            t.id: t
            for t in await self._teams.list_by_ids(list({r.team_id for r in items if r.team_id}))
        }
        ids = {r.requester_id for r in items} | {m for t in teams.values() for m in t.member_ids}
        students = await self._students.get_many(list(ids))
        result: dict[uuid.UUID, list[Participant]] = {}
        for r in items:
            team = teams.get(r.team_id) if r.team_id else None
            member_ids = team.member_ids if team else [r.requester_id]
            result[r.id] = [
                Participant(student_id=i, name=students[i].name)
                for i in member_ids
                if i in students
            ]
        return result

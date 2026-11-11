"""멘토링 팀 구성 (decisions M11·A39, 권한 mentoring.team.manage).

- 팀 멘토링을 허용한 기수에서만 만든다(설정이 없으면 404, 허용 안 함이면 422).
- 담당 멘토는 그 기수의 활성 배정이어야 하고 언제든 바꿀 수 있다
  (이미 잡힌 신청·세션은 기존 멘토 유지 — P11).
- 팀 번호는 기수별 다음 번호(유형 구분 없음, A41). 기수 설정 행을 잠가 동시 생성 번호 충돌을 막는다.
- 팀원은 그 기수 수강 중(가입 여부 무관)이어야 하고, 다른 팀에 있으면 409.
- 팀은 시간 계좌·신청이 없을 때만 삭제한다(409 `team_in_use`). 팀원은 언제든 넣고 뺀다.
모든 변경은 감사 로그를 남긴다.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.repositories import (
    CohortMentoringSettingsRepository,
    CohortMentorRepository,
    MentoringTeamRepository,
)
from app.contexts.mentoring.domain.team import MentoringTeam
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError

TARGET = "mentoring_team"


class StudentLookup(Protocol):
    """academy `StudentQueries`."""

    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...
    async def enrolled_in_cohort(self, cohort_id: uuid.UUID) -> list[Student]: ...
    async def of_user(self, user_id: uuid.UUID) -> list[Student]: ...


class MentorOfUser(Protocol):
    """educator `MentorQueries`."""

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None: ...


@dataclass(frozen=True, slots=True)
class MyTeams:
    as_student: list[MentoringTeam]
    as_mentor: list[MentoringTeam]


def _snapshot(team: MentoringTeam) -> dict[str, Any]:
    return {
        "cohort_id": str(team.cohort_id),
        "team_number": team.team_number,
        "mentor_id": str(team.mentor_id),
        "name": team.name,
        "member_ids": [str(m) for m in team.member_ids],
    }


class MentoringTeamService:
    def __init__(
        self,
        *,
        teams: MentoringTeamRepository,
        settings: CohortMentoringSettingsRepository,
        assignments: CohortMentorRepository,
        students: StudentLookup,
        mentors: MentorOfUser,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._teams = teams
        self._settings = settings
        self._assignments = assignments
        self._students = students
        self._mentors = mentors
        self._audit = audit
        self._uow = uow

    # ------------------------------------------------------------------ 조회
    async def list_by_cohort(self, cohort_id: uuid.UUID) -> list[MentoringTeam]:
        return await self._teams.list_by_cohort(cohort_id)

    async def unassigned_students(self, cohort_id: uuid.UUID) -> list[Student]:
        """팀이 없는 수강 중 수강생 (이름순)."""
        enrolled = await self._students.enrolled_in_cohort(cohort_id)
        assigned = await self._teams.team_of_students([s.id for s in enrolled])
        return [s for s in enrolled if s.id not in assigned]

    async def mine(self, user_id: uuid.UUID) -> MyTeams:
        registrations = await self._students.of_user(user_id)
        as_student = await self._teams.list_by_students([s.id for s in registrations])
        mentor = await self._mentors.get_by_user(user_id)
        as_mentor = await self._teams.list_by_mentor(mentor.id) if mentor else []
        return MyTeams(as_student=as_student, as_mentor=as_mentor)

    async def students_of(self, teams: list[MentoringTeam]) -> dict[uuid.UUID, Student]:
        return await self._students.get_many(
            list({member for team in teams for member in team.member_ids})
        )

    # ------------------------------------------------------------------ 변경
    async def create(
        self,
        cohort_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID,
        name: str | None,
        student_ids: list[uuid.UUID],
        actor_id: uuid.UUID,
    ) -> MentoringTeam:
        async with self._uow:
            settings = await self._settings.lock_by_cohort(cohort_id)
            if settings is None:
                raise NotFoundError(
                    "이 기수의 멘토링 설정이 아직 없습니다.",
                    code="mentoring_settings_not_configured",
                )
            if not settings.allow_team_mentoring:
                raise BusinessRuleViolation(
                    "팀 멘토링을 허용한 기수에서만 팀을 만들 수 있습니다.",
                    code="team_mentoring_not_allowed",
                )
            await self._ensure_assigned(mentor_id, cohort_id)
            members = list(dict.fromkeys(student_ids))
            await self._ensure_members(cohort_id, members, team_id=None)
            team = MentoringTeam(
                cohort_id=cohort_id,
                team_number=await self._teams.next_number(cohort_id),
                mentor_id=mentor_id,
                name=name,
                member_ids=members,
            )
            await self._teams.add(team)
            await self._record(actor_id, "create", team, None)
        return await self._get(cohort_id, team.id)

    async def update(
        self,
        cohort_id: uuid.UUID,
        team_id: uuid.UUID,
        changes: dict[str, Any],
        *,
        actor_id: uuid.UUID,
    ) -> MentoringTeam:
        """이름·담당 멘토를 바꾼다."""
        async with self._uow:
            team = await self._get(cohort_id, team_id)
            before = _snapshot(team)
            if "name" in changes:
                team.rename(changes["name"])
            if "mentor_id" in changes and changes["mentor_id"] != team.mentor_id:
                await self._ensure_assigned(changes["mentor_id"], cohort_id)
                team.assign_mentor(changes["mentor_id"])
            await self._teams.save(team)
            await self._record(actor_id, "update", team, before)
        return team

    async def delete(
        self, cohort_id: uuid.UUID, team_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        async with self._uow:
            team = await self._get(cohort_id, team_id)
            await self._teams.delete(team_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.team.delete",
                target_type=TARGET,
                target_id=team_id,
                before=_snapshot(team),
            )

    async def add_member(
        self,
        cohort_id: uuid.UUID,
        team_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
    ) -> MentoringTeam:
        async with self._uow:
            team = await self._get(cohort_id, team_id)
            before = _snapshot(team)
            await self._ensure_members(cohort_id, [student_id], team_id=team.id)
            team.add_member(student_id)
            await self._teams.save(team)
            await self._record(actor_id, "member_add", team, before)
        return team

    async def remove_member(
        self,
        cohort_id: uuid.UUID,
        team_id: uuid.UUID,
        student_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
    ) -> MentoringTeam:
        async with self._uow:
            team = await self._get(cohort_id, team_id)
            before = _snapshot(team)
            team.remove_member(student_id)
            await self._teams.save(team)
            await self._record(actor_id, "member_remove", team, before)
        return team

    # ------------------------------------------------------------------ 내부
    async def _get(self, cohort_id: uuid.UUID, team_id: uuid.UUID) -> MentoringTeam:
        team = await self._teams.get(team_id)
        if team is None or team.cohort_id != cohort_id:
            raise NotFoundError("팀을 찾을 수 없습니다.", code="team_not_found")
        return team

    async def _ensure_assigned(self, mentor_id: uuid.UUID, cohort_id: uuid.UUID) -> None:
        if await self._assignments.find_active(mentor_id, cohort_id) is None:
            raise BusinessRuleViolation(
                "담당 멘토는 이 기수에 활성 배정된 멘토여야 합니다.",
                code="mentor_not_assigned",
            )

    async def _ensure_members(
        self,
        cohort_id: uuid.UUID,
        student_ids: list[uuid.UUID],
        *,
        team_id: uuid.UUID | None,
    ) -> None:
        if not student_ids:
            return
        found = await self._students.get_many(student_ids)
        enrolled = {s.id for s in await self._students.enrolled_in_cohort(cohort_id)}
        for student_id in student_ids:
            if student_id not in found or found[student_id].cohort_id != cohort_id:
                raise NotFoundError("이 기수의 수강생이 아닙니다.", code="student_not_found")
            if student_id not in enrolled:
                raise BusinessRuleViolation(
                    "수강 중인 수강생만 팀에 넣을 수 있습니다.", code="student_not_enrolled"
                )
        teams = await self._teams.team_of_students(student_ids)
        if any(other != team_id for other in teams.values()):
            raise ConflictError(
                "이미 다른 팀에 속한 수강생이 있습니다.", code="student_in_other_team"
            )

    async def _record(
        self, actor_id: uuid.UUID, action: str, team: MentoringTeam, before: dict[str, Any] | None
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.team.{action}",
            target_type=TARGET,
            target_id=team.id,
            before=before,
            after=_snapshot(team),
        )

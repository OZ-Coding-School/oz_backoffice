"""운영진 최초 정보 입력(가입 신청) 유스케이스 (decisions A11).

최초 Google 로그인으로 만들어진 승인 대기 운영진이 부서·팀·직위·고용 형태·담당을 입력해 신청한다.
대기 중이면 같은 신청을 고치고, 반려됐으면 새 신청을 만든다. 승인·반려는 P3에서 만든다.
신청할 때는 팀이 부서 소속인지와 직위 담당 방식 규칙을 검사하고, 승인할 때는 존재만 검사한다 (A62).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.contexts.academy.domain.entities import Bootcamp, Cohort
from app.contexts.identity.domain.entities import User
from app.contexts.organization.domain.entities import (
    BootcampTeam,
    Department,
    EmployeePosition,
    Team,
)
from app.contexts.organization.domain.enums import EmploymentType
from app.contexts.organization.domain.registration import (
    EmployeeRegistration,
    RequestedAssignment,
    check_assignment_scope,
)
from app.contexts.organization.domain.repositories import (
    BootcampTeamRepository,
    DepartmentRepository,
    EmployeePositionRepository,
    EmployeeRegistrationRepository,
    TeamRepository,
)
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, PermissionDeniedError


class StaffTargetCatalog(Protocol):
    """담당 과정·기수 선택지 (academy `AcademyCatalog`가 구현)."""

    async def staffable_bootcamps(self) -> list[Bootcamp]: ...
    async def staffable_cohorts(self) -> list[Cohort]: ...
    async def ensure_staffable(
        self, *, bootcamp_ids: Iterable[uuid.UUID], cohort_ids: Iterable[uuid.UUID]
    ) -> None: ...


class RegistrationChoiceValidator:
    """신청·승인 항목 검증.

    - 공통(존재): 부서·팀·직위가 있고 담당 과정·기수를 고를 수 있는지
    - 신청할 때만(`strict`): 팀이 부서 소속인지, 직위 담당 방식에 맞는 담당인지 (A62)
    """

    def __init__(
        self,
        *,
        departments: DepartmentRepository,
        teams: TeamRepository,
        bootcamp_teams: BootcampTeamRepository,
        positions: EmployeePositionRepository,
        catalog: StaffTargetCatalog,
    ) -> None:
        self._departments = departments
        self._teams = teams
        self._bootcamp_teams = bootcamp_teams
        self._positions = positions
        self._catalog = catalog

    async def validate(
        self,
        *,
        department_id: uuid.UUID,
        team_id: uuid.UUID | None,
        position_id: uuid.UUID,
        assignments: list[RequestedAssignment],
        strict: bool,
    ) -> None:
        if await self._departments.get(department_id) is None:
            raise BusinessRuleViolation("존재하지 않는 부서입니다.", code="department_not_found")
        team = await self._teams.get(team_id) if team_id is not None else None
        if team_id is not None and team is None:
            raise BusinessRuleViolation("존재하지 않는 팀입니다.", code="team_not_found")
        position = await self._positions.get(position_id)
        if position is None:
            raise BusinessRuleViolation("존재하지 않는 직위입니다.", code="position_not_found")
        await self._catalog.ensure_staffable(
            bootcamp_ids=[a.bootcamp_id for a in assignments if a.bootcamp_id],
            cohort_ids=[a.cohort_id for a in assignments if a.cohort_id],
        )
        if not strict:
            return
        if team is not None and team.department_id != department_id:
            raise BusinessRuleViolation(
                "선택한 부서에 속한 팀이 아닙니다.", code="team_not_in_department"
            )
        team_bootcamp_ids = (
            await self._bootcamp_teams.list_bootcamp_ids(team.id) if team is not None else set()
        )
        cohort_bootcamps = (
            {c.id: c.bootcamp_id for c in await self._catalog.staffable_cohorts()}
            if any(a.cohort_id for a in assignments)
            else {}
        )
        check_assignment_scope(
            position.assignment_scope,
            assignments,
            team_bootcamp_ids=team_bootcamp_ids,
            cohort_bootcamps=cohort_bootcamps,
        )


@dataclass(frozen=True, slots=True)
class RegistrationOptions:
    departments: list[Department]
    teams: list[Team]
    bootcamp_teams: list[BootcampTeam]
    positions: list[EmployeePosition]
    bootcamps: list[Bootcamp]
    cohorts: list[Cohort]


class StaffRegistrationService:
    def __init__(
        self,
        *,
        registrations: EmployeeRegistrationRepository,
        departments: DepartmentRepository,
        teams: TeamRepository,
        bootcamp_teams: BootcampTeamRepository,
        positions: EmployeePositionRepository,
        catalog: StaffTargetCatalog,
        uow: UnitOfWork,
        staff_email_domain: str,
    ) -> None:
        self._registrations = registrations
        self._departments = departments
        self._teams = teams
        self._bootcamp_teams = bootcamp_teams
        self._positions = positions
        self._catalog = catalog
        self._uow = uow
        self._staff_suffix = f"@{staff_email_domain.lower()}"

    async def options(self, applicant: User) -> RegistrationOptions:
        self._ensure_staff_account(applicant)
        return RegistrationOptions(
            departments=await self._departments.list_all(),
            teams=await self._teams.list_all(),
            bootcamp_teams=await self._bootcamp_teams.list_all(),
            positions=await self._positions.list_all(),
            bootcamps=await self._catalog.staffable_bootcamps(),
            cohorts=await self._catalog.staffable_cohorts(),
        )

    async def get_mine(self, applicant: User) -> EmployeeRegistration | None:
        self._ensure_staff_account(applicant)
        return await self._registrations.get_latest_by_user(applicant.id)

    async def submit(
        self,
        applicant: User,
        *,
        department_id: uuid.UUID,
        team_id: uuid.UUID | None,
        position_id: uuid.UUID,
        employment_type: EmploymentType,
        assignments: list[RequestedAssignment],
    ) -> EmployeeRegistration:
        self._ensure_staff_account(applicant)
        if applicant.is_approved:
            raise ConflictError("이미 승인된 계정입니다.", code="user_already_approved")
        await RegistrationChoiceValidator(
            departments=self._departments,
            teams=self._teams,
            bootcamp_teams=self._bootcamp_teams,
            positions=self._positions,
            catalog=self._catalog,
        ).validate(
            department_id=department_id,
            team_id=team_id,
            position_id=position_id,
            assignments=assignments,
            strict=True,
        )

        async with self._uow:
            latest = await self._registrations.get_latest_by_user(applicant.id)
            if latest is not None and latest.is_pending:
                latest.update(
                    department_id=department_id,
                    team_id=team_id,
                    position_id=position_id,
                    employment_type=employment_type,
                    assignments=assignments,
                )
                await self._registrations.save(latest)
                return latest
            registration = EmployeeRegistration(
                user_id=applicant.id,
                department_id=department_id,
                team_id=team_id,
                position_id=position_id,
                employment_type=employment_type,
                assignments=assignments,
            )
            await self._registrations.add(registration)
            return registration

    def _ensure_staff_account(self, user: User) -> None:
        if not user.email.endswith(self._staff_suffix):
            raise PermissionDeniedError(
                "운영진 계정만 이용할 수 있습니다.", code="not_staff_account"
            )

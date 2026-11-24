"""역할 보유자 목록 (decisions A85, BE-3e). 권한: role.assign.

멘토·수강생을 뺀 역할을 가진 회원을 이름순으로, 회원마다 가진 역할(만료 포함)을 함께 준다.
회원 이름·이메일은 identity, 소속은 organization, 과정·기수 이름은 academy 공개 서비스에서 읽는다.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from app.contexts.access.domain.catalog import HIDDEN_ROLE_CODES
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.domain.repositories import RoleRepository, UserRoleRepository
from app.contexts.access.domain.roles import is_directly_managed
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock


class HolderUsers(Protocol):
    """identity `UserQueries`가 구현."""

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]: ...


class Affiliation(Protocol):
    @property
    def department_name(self) -> str | None: ...
    @property
    def team_name(self) -> str | None: ...
    @property
    def position_name(self) -> str | None: ...


class HolderAffiliations(Protocol):
    """organization `EmployeeQueries`가 구현."""

    async def affiliations(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, Affiliation]: ...


class CohortName(Protocol):
    @property
    def bootcamp_name(self) -> str: ...
    @property
    def cohort_number(self) -> int: ...


class ScopeNames(Protocol):
    """academy `AcademyCatalog`가 구현."""

    async def bootcamp_names(self, bootcamp_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]: ...
    async def cohort_labels(
        self, cohort_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, CohortName]: ...


@dataclass(frozen=True, slots=True)
class HolderRole:
    user_role: UserRole
    role_name: str
    bootcamp_name: str | None
    cohort_number: int | None
    is_effective: bool
    managed_by: Literal["direct", "assignment"]


@dataclass(frozen=True, slots=True)
class RoleHolder:
    user: User
    affiliation: Affiliation | None
    roles: list[HolderRole]


class RoleHolderQueries:
    def __init__(
        self,
        *,
        user_roles: UserRoleRepository,
        roles: RoleRepository,
        users: HolderUsers,
        affiliations: HolderAffiliations,
        scopes: ScopeNames,
        clock: Clock,
    ) -> None:
        self._user_roles = user_roles
        self._roles = roles
        self._users = users
        self._affiliations = affiliations
        self._scopes = scopes
        self._clock = clock

    async def list(
        self, *, role_code: str | None, query: str | None, limit: int, offset: int
    ) -> tuple[list[RoleHolder], int]:
        user_ids, total = await self._user_roles.list_holder_ids(
            exclude_roles=HIDDEN_ROLE_CODES,
            role_code=role_code,
            query=(query or "").strip() or None,
            limit=limit,
            offset=offset,
        )
        if not user_ids:
            return [], total
        grants = await self._user_roles.list_by_users(user_ids, exclude_roles=HIDDEN_ROLE_CODES)
        names = {role.code: role.name for role in await self._roles.list_all()}
        users = await self._users.get_many(user_ids)
        affiliations = await self._affiliations.affiliations(user_ids)
        bootcamps = await self._scopes.bootcamp_names(
            {g.scope_id for g in grants if g.scope_type is RoleScopeType.BOOTCAMP and g.scope_id}
        )
        cohorts = await self._scopes.cohort_labels(
            {g.scope_id for g in grants if g.scope_type is RoleScopeType.COHORT and g.scope_id}
        )
        now = self._clock.now()

        by_user: dict[uuid.UUID, list[HolderRole]] = {}
        for g in grants:
            cohort = cohorts.get(g.scope_id) if g.scope_id else None
            by_user.setdefault(g.user_id, []).append(
                HolderRole(
                    user_role=g,
                    role_name=names.get(g.role_code, g.role_code),
                    bootcamp_name=(
                        cohort.bootcamp_name
                        if cohort
                        else bootcamps.get(g.scope_id)
                        if g.scope_id
                        else None
                    ),
                    cohort_number=cohort.cohort_number if cohort else None,
                    is_effective=g.is_effective(now),
                    managed_by="direct" if is_directly_managed(g.role_code) else "assignment",
                )
            )
        return [
            RoleHolder(user=users[uid], affiliation=affiliations.get(uid), roles=by_user[uid])
            for uid in user_ids
            if uid in users and uid in by_user
        ], total

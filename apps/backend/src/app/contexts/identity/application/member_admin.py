"""전체 회원 조회·비활성화·활성화 (decisions A94)."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.domain.entities import AuditLog
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType
from app.contexts.identity.domain.repositories import UserRepository
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError, NotFoundError

DEACTIVATE = "member.user.deactivate"
ACTIVATE = "member.user.activate"
REASON_MAX_LENGTH = 300


@dataclass(frozen=True, slots=True)
class MemberEnrollment:
    bootcamp_name: str
    cohort_number: int
    status: str


@dataclass(frozen=True, slots=True)
class MemberAssignment:
    bootcamp_name: str
    cohort_number: int
    active: bool


@dataclass(frozen=True, slots=True)
class MemberLinks:
    """계정 종류별 연결 정보 (A94). 종류와 상관없는 칸은 비어 있다."""

    enrollments: list[MemberEnrollment] = field(default_factory=list)
    assignments: list[MemberAssignment] = field(default_factory=list)
    contract_count: int | None = None
    department_name: str | None = None
    team_name: str | None = None
    position_name: str | None = None


class MemberLinksReader(Protocol):
    """여러 컨텍스트의 연결 정보를 모은다 (app/composition에서 구현)."""

    async def links_of(self, user: User) -> MemberLinks: ...


class AuditReader(Protocol):
    async def list_for_target(
        self, target_type: str, target_id: uuid.UUID, *, actions: frozenset[str], limit: int = 50
    ) -> list[AuditLog]: ...


class SessionRevoker(Protocol):
    async def revoke_all(self, user_id: uuid.UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class MemberEvent:
    """비활성화·활성화 이력"""

    deactivated: bool
    reason: str | None
    actor_user_id: uuid.UUID | None
    at: datetime


@dataclass(frozen=True, slots=True)
class MemberDetail:
    user: User
    links: MemberLinks
    history: list[MemberEvent]


class MemberAdministration:
    def __init__(
        self,
        *,
        users: UserRepository,
        links: MemberLinksReader,
        audit: AuditRecorder,
        audit_reader: AuditReader,
        uow: UnitOfWork,
    ) -> None:
        self._users = users
        self._links = links
        self._audit = audit
        self._audit_reader = audit_reader
        self._uow = uow

    async def search(
        self,
        *,
        account_type: AccountType | None,
        query: str | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int, dict[AccountType, int]]:
        q = (query or "").strip() or None
        users, total = await self._users.search_approved(
            account_type=account_type, query=q, active=active, limit=limit, offset=offset
        )
        return users, total, await self._users.count_approved_by_type(query=q, active=active)

    async def detail(self, user_id: uuid.UUID) -> MemberDetail:
        user = await self._get(user_id)
        logs = await self._audit_reader.list_for_target(
            "user", user_id, actions=frozenset({DEACTIVATE, ACTIVATE})
        )
        history = [
            MemberEvent(
                deactivated=log.action == DEACTIVATE,
                reason=(log.after or {}).get("reason"),
                actor_user_id=log.actor_user_id,
                at=log.created_at,
            )
            for log in logs
        ]
        return MemberDetail(user=user, links=await self._links.links_of(user), history=history)

    async def deactivate(
        self, user_id: uuid.UUID, reason: str, *, actor_id: uuid.UUID, sessions: SessionRevoker
    ) -> User:
        """로그인을 막고(A94) 커밋 뒤 refresh 토큰을 모두 폐기한다.

        자기 자신·마지막 최고 관리자는 409.
        """
        if user_id == actor_id:
            raise ConflictError(
                "자기 계정은 비활성화할 수 없습니다.", code="cannot_deactivate_self"
            )
        async with self._uow:
            user = await self._get(user_id)
            if user.is_super_admin and set(await self._users.lock_super_admin_ids()) == {user_id}:
                raise ConflictError(
                    "마지막 최고 관리자는 비활성화할 수 없습니다.", code="last_super_admin"
                )
            if user.is_active:
                user.deactivate()
                await self._users.save(user)
                await self._audit.record(
                    actor_user_id=actor_id,
                    action=DEACTIVATE,
                    target_type="user",
                    target_id=user_id,
                    after={"is_active": False, "reason": reason},
                )
        await sessions.revoke_all(user_id)
        return user

    async def activate(
        self, user_id: uuid.UUID, reason: str | None, *, actor_id: uuid.UUID
    ) -> User:
        async with self._uow:
            user = await self._get(user_id)
            if not user.is_active:
                user.activate()
                await self._users.save(user)
                await self._audit.record(
                    actor_user_id=actor_id,
                    action=ACTIVATE,
                    target_type="user",
                    target_id=user_id,
                    after={"is_active": True, "reason": reason},
                )
        return user

    async def _get(self, user_id: uuid.UUID) -> User:
        user = await self._users.get(user_id)
        if user is None or user.deleted_at is not None or not user.is_approved:
            raise NotFoundError("회원을 찾을 수 없습니다.", code="user_not_found")
        return user

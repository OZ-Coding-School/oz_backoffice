"""identity 리포지토리 인터페이스."""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import AccountType, MemberSignupType, SocialLoginProvider
from app.contexts.identity.domain.signup import MemberSignup


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def save(self, user: User) -> None: ...

    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def list_by_ids(self, user_ids: list[uuid.UUID]) -> list[User]: ...

    async def get_by_phone(self, phone_number: str) -> User | None: ...

    async def add_oauth_account(self, account: OAuthAccount) -> None: ...

    async def get_by_oauth(
        self, provider: SocialLoginProvider, provider_user_id: str
    ) -> User | None: ...

    async def lock_super_admin_ids(self) -> list[uuid.UUID]:
        """최고 관리자 행을 잠가 읽는다 (UoW 안에서)."""
        ...

    async def search_approved(
        self,
        *,
        account_type: AccountType | None,
        query: str | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        """승인된 계정(탈퇴 제외), 가입 승인 최신순. query는 이름·이메일·휴대폰 (A94)."""
        ...

    async def count_approved_by_type(
        self, *, query: str | None, active: bool | None
    ) -> dict[AccountType, int]:
        """승인된 계정의 종류별 수 (목록 탭 건수)."""
        ...


@dataclass(frozen=True, slots=True)
class SignupVisibility:
    """승인 대기 목록에서 볼 수 있는 범위 (운영진 권한에서 계산)."""

    all_students: bool = False
    student_cohort_ids: frozenset[uuid.UUID] = frozenset()
    student_bootcamp_ids: frozenset[uuid.UUID] = frozenset()  # 그 과정의 기수 전부
    mentors: bool = False


@dataclass(frozen=True, slots=True)
class PendingSignupFilter:
    visibility: SignupVisibility
    signup_type: MemberSignupType | None = None
    cohort_id: uuid.UUID | None = None


class MemberSignupRepository(Protocol):
    async def add(self, signup: MemberSignup) -> None: ...

    async def save(self, signup: MemberSignup) -> None: ...

    async def get(self, signup_id: uuid.UUID) -> MemberSignup | None: ...

    async def get_latest_by_user(self, user_id: uuid.UUID) -> MemberSignup | None: ...

    async def get_pending_by_user(self, user_id: uuid.UUID) -> MemberSignup | None: ...

    async def list_pending(
        self, signup_filter: PendingSignupFilter, *, limit: int, offset: int
    ) -> tuple[list[MemberSignup], int]:
        """오래된 신청부터."""
        ...

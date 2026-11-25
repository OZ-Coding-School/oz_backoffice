"""identity 인메모리 리포지토리·연동 가짜 구현."""

import uuid
from dataclasses import replace

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import AccountType, SocialLoginProvider
from app.contexts.identity.domain.repositories import PendingSignupFilter
from app.contexts.identity.domain.signup import MemberSignup
from app.integrations.google.oauth import GoogleIdentity
from app.shared.errors import AuthenticationError


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.oauth_accounts: list[OAuthAccount] = []

    async def lock_super_admin_ids(self) -> list[uuid.UUID]:
        return [u.id for u in self.users.values() if u.is_super_admin and u.deleted_at is None]

    def _approved(self, query: str | None, active: bool | None) -> list[User]:
        q = (query or "").lower()
        return [
            u
            for u in self.users.values()
            if u.is_approved
            and u.deleted_at is None
            and (active is None or u.is_active == active)
            and (not q or q in u.name.lower() or q in u.email.lower())
        ]

    async def search_approved(
        self,
        *,
        account_type: AccountType | None,
        query: str | None,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        found = [u for u in self._approved(query, active) if account_type in (None, u.account_type)]
        return [replace(u) for u in found[offset : offset + limit]], len(found)

    async def count_approved_by_type(
        self, *, query: str | None, active: bool | None
    ) -> dict[AccountType, int]:
        counts = {t: 0 for t in AccountType}
        for u in self._approved(query, active):
            counts[u.account_type] += 1
        return counts

    async def add(self, user: User) -> None:
        self.users[user.id] = replace(user)

    async def save(self, user: User) -> None:
        self.users[user.id] = replace(user)

    async def get(self, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user else None

    async def list_by_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        return [replace(self.users[i]) for i in user_ids if i in self.users]

    async def get_by_email(self, email: str) -> User | None:
        email = email.strip().lower()
        return next((replace(u) for u in self.users.values() if u.email == email), None)

    async def get_by_phone(self, phone_number: str) -> User | None:
        return next(
            (replace(u) for u in self.users.values() if u.phone_number == phone_number), None
        )

    async def add_oauth_account(self, account: OAuthAccount) -> None:
        self.oauth_accounts.append(account)

    async def get_by_oauth(
        self, provider: SocialLoginProvider, provider_user_id: str
    ) -> User | None:
        for account in self.oauth_accounts:
            if account.provider is provider and account.provider_user_id == provider_user_id:
                return await self.get(account.user_id)
        return None


class FakeGoogleAuthenticator:
    """code → GoogleIdentity 고정 응답. 등록되지 않은 code는 인증 실패."""

    def __init__(self) -> None:
        self.identities: dict[str, GoogleIdentity] = {}
        self.exchanged: list[tuple[str, str]] = []

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        return f"https://accounts.google.test/auth?state={state}&code_challenge={code_challenge}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> GoogleIdentity:
        self.exchanged.append((code, code_verifier))
        if code not in self.identities:
            raise AuthenticationError("Google 인증에 실패했습니다.", code="google_auth_failed")
        return self.identities[code]


class InMemoryMemberSignupRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, MemberSignup] = {}

    async def add(self, signup: MemberSignup) -> None:
        self.items[signup.id] = signup

    async def save(self, signup: MemberSignup) -> None:
        self.items[signup.id] = signup

    async def get(self, signup_id: uuid.UUID) -> MemberSignup | None:
        return self.items.get(signup_id)

    async def get_latest_by_user(self, user_id: uuid.UUID) -> MemberSignup | None:
        mine = [s for s in self.items.values() if s.user_id == user_id]
        return max(mine, key=lambda s: s.id) if mine else None

    async def get_pending_by_user(self, user_id: uuid.UUID) -> MemberSignup | None:
        return next((s for s in self.items.values() if s.user_id == user_id and s.is_pending), None)

    async def list_pending(
        self, signup_filter: PendingSignupFilter, *, limit: int, offset: int
    ) -> tuple[list[MemberSignup], int]:
        pending = sorted((s for s in self.items.values() if s.is_pending), key=lambda s: s.id)
        return pending[offset : offset + limit], len(pending)

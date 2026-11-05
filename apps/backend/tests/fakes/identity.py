"""identity 인메모리 리포지토리·연동 가짜 구현."""

import uuid
from dataclasses import replace

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import SocialLoginProvider
from app.integrations.google.oauth import GoogleIdentity
from app.shared.errors import AuthenticationError


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.oauth_accounts: list[OAuthAccount] = []

    async def add(self, user: User) -> None:
        self.users[user.id] = replace(user)

    async def save(self, user: User) -> None:
        self.users[user.id] = replace(user)

    async def get(self, user_id: uuid.UUID) -> User | None:
        user = self.users.get(user_id)
        return replace(user) if user else None

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

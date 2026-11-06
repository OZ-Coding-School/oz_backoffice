"""identity 리포지토리 인터페이스."""

import uuid
from typing import Protocol

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import SocialLoginProvider


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

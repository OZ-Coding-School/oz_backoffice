"""identity 리포지토리 구현 (Tortoise)."""

import uuid

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import SocialLoginProvider
from app.contexts.identity.infrastructure.models import OAuthAccountModel, UserModel

_USER_FIELDS = (
    "email",
    "hashed_password",
    "name",
    "phone_number",
    "birth_date",
    "approval_status",
    "approved_at",
    "email_verified_at",
    "phone_verified_at",
    "is_active",
    "last_login_at",
    "deleted_at",
)


def _to_entity(model: UserModel) -> User:
    return User(id=model.id, **{name: getattr(model, name) for name in _USER_FIELDS})


def _apply(model: UserModel, user: User) -> None:
    for name in _USER_FIELDS:
        setattr(model, name, getattr(user, name))


class TortoiseUserRepository:
    async def add(self, user: User) -> None:
        model = UserModel(id=user.id)
        _apply(model, user)
        await model.save(force_create=True)

    async def save(self, user: User) -> None:
        model = await UserModel.get(id=user.id)
        _apply(model, user)
        await model.save()

    async def get(self, user_id: uuid.UUID) -> User | None:
        model = await UserModel.get_or_none(id=user_id)
        return _to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        model = await UserModel.get_or_none(email=email.strip().lower())
        return _to_entity(model) if model else None

    async def get_by_phone(self, phone_number: str) -> User | None:
        model = await UserModel.get_or_none(phone_number=phone_number)
        return _to_entity(model) if model else None

    async def add_oauth_account(self, account: OAuthAccount) -> None:
        await OAuthAccountModel.create(
            id=account.id,
            user_id=account.user_id,
            provider=account.provider,
            oauth_provider_id=account.provider_user_id,
        )

    async def get_by_oauth(
        self, provider: SocialLoginProvider, provider_user_id: str
    ) -> User | None:
        account = (
            await OAuthAccountModel.filter(provider=provider, oauth_provider_id=provider_user_id)
            .select_related("user")
            .first()
        )
        return _to_entity(account.user) if account else None

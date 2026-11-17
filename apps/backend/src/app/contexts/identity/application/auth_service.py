"""인증 유스케이스: 운영진 Google 로그인, 토큰 갱신·로그아웃, 현재 사용자 확인."""

import secrets
import uuid
from dataclasses import dataclass

from app.contexts.identity.application.ports import GoogleAuthenticator
from app.contexts.identity.application.tokens import IssuedAccess, IssuedTokens, TokenService
from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import SocialLoginProvider
from app.contexts.identity.domain.repositories import UserRepository
from app.contexts.identity.domain.sessions import OAuthStateStore
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.integrations.google.oauth import GoogleIdentity, new_pkce_pair
from app.shared.errors import AuthenticationError

_NAME_MAX_LENGTH = 50


def _account_disabled() -> AuthenticationError:
    return AuthenticationError(
        "사용할 수 없는 계정입니다. 관리자에게 문의해 주세요.", code="account_disabled"
    )


def _display_name(identity: GoogleIdentity) -> str:
    name = identity.name or identity.email.split("@", 1)[0]
    return name.strip()[:_NAME_MAX_LENGTH]


@dataclass(frozen=True, slots=True)
class LoginStart:
    authorization_url: str
    state: str  # 브라우저 쿠키에 담아 콜백에서 대조한다 (로그인 CSRF 방지)


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    tokens: IssuedTokens


class StaffGoogleLoginService:
    """운영진 Google 로그인 (decisions A1, A11).

    도메인 계정이면 처음 로그인할 때 승인 대기(PENDING) 회원을 만든다.
    부서·직위·담당 입력과 관리자 승인을 거쳐야 백오피스 기능을 쓸 수 있다.
    """

    def __init__(
        self,
        *,
        google: GoogleAuthenticator,
        states: OAuthStateStore,
        users: UserRepository,
        tokens: TokenService,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._google = google
        self._states = states
        self._users = users
        self._tokens = tokens
        self._uow = uow
        self._clock = clock

    async def start(self) -> LoginStart:
        """인가 URL을 만든다. state와 PKCE verifier는 콜백에서 한 번만 쓸 수 있게 저장한다.

        state는 호출한 쪽이 브라우저 쿠키로도 내려보내, 콜백에서 같은 브라우저인지 확인한다.
        """
        state = secrets.token_urlsafe(32)
        pkce = new_pkce_pair()
        await self._states.save(state, pkce.verifier)
        url = self._google.authorization_url(state=state, code_challenge=pkce.challenge)
        return LoginStart(authorization_url=url, state=state)

    async def complete(self, *, code: str, state: str, browser_state: str | None) -> LoginResult:
        """Google 콜백 처리. state는 로그인을 시작한 브라우저의 쿠키 값과 같아야 한다."""
        if not browser_state or not secrets.compare_digest(state.encode(), browser_state.encode()):
            raise AuthenticationError(
                "로그인 요청이 만료되었습니다. 다시 시도해 주세요.", code="oauth_state_invalid"
            )
        verifier = await self._states.pop(state)
        if verifier is None:
            raise AuthenticationError(
                "로그인 요청이 만료되었습니다. 다시 시도해 주세요.", code="oauth_state_invalid"
            )
        identity = await self._google.exchange_code(code=code, code_verifier=verifier)

        now = self._clock.now()
        async with self._uow:
            user = await self._users.get_by_oauth(SocialLoginProvider.GOOGLE, identity.subject)
            if user is None:
                user = await self._users.get_by_email(identity.email)
                if user is None:
                    user = User(
                        email=identity.email, name=_display_name(identity), email_verified_at=now
                    )
                    await self._users.add(user)
                await self._users.add_oauth_account(
                    OAuthAccount(
                        user_id=user.id,
                        provider=SocialLoginProvider.GOOGLE,
                        provider_user_id=identity.subject,
                    )
                )
            if not user.can_login:
                raise _account_disabled()
            user.record_login(now=now)
            await self._users.save(user)

        return LoginResult(user=user, tokens=await self._tokens.issue(user.id))


class SessionService:
    """토큰 갱신·로그아웃."""

    def __init__(self, *, users: UserRepository, tokens: TokenService) -> None:
        self._users = users
        self._tokens = tokens

    async def refresh(self, refresh_token: str) -> IssuedTokens | IssuedAccess:
        """회전하면 새 access·refresh, 재사용 유예(A60)면 access만 돌려준다."""
        consumed = await self._tokens.consume_refresh(refresh_token)
        user = await self._users.get(consumed.user_id)
        if user is None or not user.can_login:
            await self._tokens.revoke_all(consumed.user_id)
            raise _account_disabled()
        if not consumed.rotated:
            return self._tokens.issue_access(consumed.user_id)
        return await self._tokens.issue(consumed.user_id)

    async def logout(self, refresh_token: str) -> None:
        await self._tokens.revoke(refresh_token)


class UserQueries:
    """다른 컨텍스트(access의 인증 의존성 등)가 쓰는 공개 조회 서비스."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def get_authenticated(self, user_id: uuid.UUID) -> User:
        """access 토큰의 사용자를 확인한다. 탈퇴·정지된 계정이면 401."""
        user = await self._users.get(user_id)
        if user is None:
            raise AuthenticationError("유효하지 않은 토큰입니다.", code="token_invalid")
        if not user.can_login:
            raise _account_disabled()
        return user

    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
        """목록 화면용 일괄 조회 (N+1 방지)."""
        return {user.id: user for user in await self._users.list_by_ids(list(set(user_ids)))}

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._users.get(user_id)

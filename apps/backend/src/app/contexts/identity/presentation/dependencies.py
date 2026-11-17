"""identity 서비스 조립."""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.contexts.identity.application.auth_service import SessionService, StaffGoogleLoginService
from app.contexts.identity.application.ports import GoogleAuthenticator
from app.contexts.identity.application.tokens import TokenService
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.identity.infrastructure.token_store import (
    RedisOAuthStateStore,
    RedisRefreshTokenStore,
)
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock, get_http_client, get_jwt_service
from app.core.redis import get_redis
from app.core.security import JWTService
from app.core.uow import UnitOfWork
from app.integrations.google.oauth import GoogleOAuthClient
from app.shared.errors import ServiceUnavailableError

SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RedisDep = Annotated[Redis, Depends(get_redis)]
ClockDep = Annotated[Clock, Depends(get_clock)]


def get_google_authenticator(request: Request, settings: SettingsDep) -> GoogleAuthenticator:
    # 설정 확인을 먼저 한다 (미설정이면 HTTP 클라이언트 없이 503)
    if not settings.google_client_id:
        raise ServiceUnavailableError(
            "Google 로그인이 설정되지 않았습니다.", code="google_login_not_configured"
        )
    return GoogleOAuthClient(
        get_http_client(request),
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        redirect_uri=settings.google_redirect_uri,
        hosted_domain=settings.google_allowed_domain,
    )


def get_token_service(
    settings: SettingsDep,
    redis: RedisDep,
    clock: ClockDep,
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
) -> TokenService:
    store = RedisRefreshTokenStore(redis, ttl_seconds=settings.refresh_token_ttl_seconds)
    return TokenService(jwt, store, clock, reuse_grace_seconds=settings.refresh_reuse_grace_seconds)


TokensDep = Annotated[TokenService, Depends(get_token_service)]


def get_staff_login_service(
    google: Annotated[GoogleAuthenticator, Depends(get_google_authenticator)],
    redis: RedisDep,
    tokens: TokensDep,
    clock: ClockDep,
) -> StaffGoogleLoginService:
    return StaffGoogleLoginService(
        google=google,
        states=RedisOAuthStateStore(redis),
        users=TortoiseUserRepository(),
        tokens=tokens,
        uow=UnitOfWork(),
        clock=clock,
    )


def get_session_service(tokens: TokensDep) -> SessionService:
    return SessionService(users=TortoiseUserRepository(), tokens=tokens)

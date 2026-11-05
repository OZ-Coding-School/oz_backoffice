"""인증(/auth)과 내 정보(/me) API.

refresh 토큰은 HttpOnly 쿠키(`oz_refresh`, Path=/api/v1/auth)로만 주고받는다 (plan §2.1).
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.contexts.access.presentation.dependencies import CurrentUser
from app.contexts.identity.application.auth_service import SessionService, StaffGoogleLoginService
from app.contexts.identity.application.tokens import IssuedTokens
from app.contexts.identity.presentation.dependencies import (
    SettingsDep,
    get_session_service,
    get_staff_login_service,
)
from app.contexts.identity.presentation.schemas import (
    AccessTokenResponse,
    AuthorizationUrlResponse,
    GoogleCallbackRequest,
    MeResponse,
)
from app.core.config import Settings
from app.shared.errors import AuthenticationError

REFRESH_COOKIE = "oz_refresh"

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])

LoginServiceDep = Annotated[StaffGoogleLoginService, Depends(get_staff_login_service)]
SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _cookie_path(settings: Settings) -> str:
    return f"{settings.api_prefix}/auth"


def _respond_with_tokens(
    response: Response, tokens: IssuedTokens, settings: Settings
) -> AccessTokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path=_cookie_path(settings),
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return AccessTokenResponse(
        access_token=tokens.access_token, expires_at=tokens.access_expires_at
    )


@auth_router.get("/google/authorize", response_model=AuthorizationUrlResponse)
async def google_authorize(service: LoginServiceDep) -> AuthorizationUrlResponse:
    return AuthorizationUrlResponse(authorization_url=await service.start())


@auth_router.post("/google/callback", response_model=AccessTokenResponse)
async def google_callback(
    body: GoogleCallbackRequest,
    response: Response,
    service: LoginServiceDep,
    settings: SettingsDep,
) -> AccessTokenResponse:
    result = await service.complete(code=body.code, state=body.state)
    return _respond_with_tokens(response, result.tokens, settings)


@auth_router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    response: Response,
    service: SessionServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> AccessTokenResponse:
    if not refresh_token:
        raise AuthenticationError("로그인이 필요합니다.", code="refresh_token_missing")
    tokens = await service.refresh(refresh_token)
    return _respond_with_tokens(response, tokens, settings)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    service: SessionServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> Response:
    if refresh_token:
        await service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=_cookie_path(settings),
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@me_router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    """승인 전에도 호출할 수 있다 (승인 상태 확인용, plan §2.2)."""
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        phone_number=user.phone_number,
        approval_status=user.approval_status,
        approved_at=user.approved_at,
    )

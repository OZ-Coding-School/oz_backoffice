"""인증(/auth)과 내 정보(/me) API.

- Google 로그인은 백엔드가 콜백을 받는다 (decisions A15).
  프론트는 브라우저를 `/auth/google/login`으로 이동시키고,
  로그인이 끝나 프론트로 돌아오면 `/auth/refresh`로 access 토큰을 받는다.
- refresh 토큰은 HttpOnly 쿠키(`oz_refresh`, Path=/api/v1/auth)로만 주고받는다 (plan §2.1).
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, Response, status
from fastapi.responses import RedirectResponse

from app.contexts.access.application.roles import RoleQueries
from app.contexts.access.presentation.dependencies import CurrentUser, get_role_queries
from app.contexts.identity.application.auth_service import SessionService, StaffGoogleLoginService
from app.contexts.identity.application.tokens import IssuedAccess, IssuedTokens
from app.contexts.identity.presentation.dependencies import (
    SettingsDep,
    get_session_service,
    get_staff_login_service,
)
from app.contexts.identity.presentation.schemas import (
    AccessTokenResponse,
    MeResponse,
    RoleGrantResponse,
)
from app.core.config import Settings
from app.shared.errors import AppError, AuthenticationError

REFRESH_COOKIE = "oz_refresh"
STATE_COOKIE = "oz_oauth_state"
STATE_COOKIE_MAX_AGE = 600  # Redis에 저장한 state·PKCE verifier 수명과 같다

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])

LoginServiceDep = Annotated[StaffGoogleLoginService, Depends(get_staff_login_service)]
SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _cookie_path(settings: Settings) -> str:
    return f"{settings.api_prefix}/auth"


def _state_cookie_path(settings: Settings) -> str:
    return f"{settings.api_prefix}/auth/google"


def _set_refresh_cookie(response: Response, tokens: IssuedTokens, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path=_cookie_path(settings),
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def respond_with_tokens(
    response: Response, tokens: IssuedTokens, settings: Settings
) -> AccessTokenResponse:
    _set_refresh_cookie(response, tokens, settings)
    response.headers["Cache-Control"] = "no-store"
    return AccessTokenResponse(
        access_token=tokens.access_token, expires_at=tokens.access_expires_at
    )


@auth_router.get("/google/login", status_code=status.HTTP_302_FOUND)
async def google_login(service: LoginServiceDep, settings: SettingsDep) -> RedirectResponse:
    """브라우저를 이 주소로 이동시키면 Google 로그인 화면으로 보낸다 (decisions A15).

    state를 HttpOnly 쿠키로 내려보내 콜백에서 같은 브라우저인지 확인한다(로그인 CSRF 방지).
    """
    started = await service.start()
    response = RedirectResponse(started.authorization_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        STATE_COOKIE,
        started.state,
        max_age=STATE_COOKIE_MAX_AGE,
        path=_state_cookie_path(settings),
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",  # Google에서 돌아오는 최상위 GET 이동에는 Lax 쿠키가 실린다
    )
    return response


@auth_router.get("/google/callback", status_code=status.HTTP_302_FOUND)
async def google_callback(
    service: LoginServiceDep,
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    browser_state: Annotated[str | None, Cookie(alias=STATE_COOKIE)] = None,
) -> RedirectResponse:
    """Google이 돌려보내는 콜백. 결과와 상관없이 프론트엔드로 302 리디렉션한다.

    - 성공: refresh 쿠키를 설정하고 `{FRONTEND_BASE_URL}/`로 보낸다.
      프론트는 `/auth/refresh`로 access 토큰을 받는다.
    - 실패: `{FRONTEND_BASE_URL}/login?error=<code>`로 보낸다.
    """
    try:
        if error or not code or not state:
            raise AuthenticationError(
                "Google 로그인이 취소되었습니다.", code="google_login_cancelled"
            )
        result = await service.complete(code=code, state=state, browser_state=browser_state)
    except AppError as exc:
        response = RedirectResponse(
            f"{settings.frontend_base_url}/login?{urlencode({'error': exc.code})}",
            status_code=status.HTTP_302_FOUND,
        )
    else:
        response = RedirectResponse(
            f"{settings.frontend_base_url}/", status_code=status.HTTP_302_FOUND
        )
        _set_refresh_cookie(response, result.tokens, settings)
    response.delete_cookie(
        STATE_COOKIE,
        path=_state_cookie_path(settings),
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


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
    if isinstance(tokens, IssuedAccess):
        # 재사용 유예(A60): refresh 쿠키는 그대로 두고 access만 준다
        response.headers["Cache-Control"] = "no-store"
        return AccessTokenResponse(
            access_token=tokens.access_token, expires_at=tokens.access_expires_at
        )
    return respond_with_tokens(response, tokens, settings)


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
async def me(
    user: CurrentUser, role_queries: Annotated[RoleQueries, Depends(get_role_queries)]
) -> MeResponse:
    """승인 전에도 호출할 수 있다 (승인 상태 확인용, plan §2.2). 만료되지 않은 역할을 함께 준다."""
    grants = await role_queries.list_for_user(user.id)
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        phone_number=user.phone_number,
        approval_status=user.approval_status,
        approved_at=user.approved_at,
        roles=[
            RoleGrantResponse(
                role=g.role_code,
                scope_type=g.scope_type,
                scope_id=g.scope_id,
                expires_at=g.expires_at,
            )
            for g in grants
        ],
    )

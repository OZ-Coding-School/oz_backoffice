"""수강생·멘토 이메일 + 비밀번호 로그인과 비밀번호 재설정 API (decisions A32).

POST /auth/login                 → access 토큰(본문) + refresh 쿠키 (운영진 로그인과 같은 방식)
POST /auth/password-reset/code   → 항상 204 (가입 여부를 드러내지 않음)
POST /auth/password-reset        → 코드 확인 후 새 비밀번호 (204)
"""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.password_auth import (
    PasswordLoginService,
    PasswordResetService,
    dummy_hash,
)
from app.contexts.identity.application.verification_codes import VerificationCodes
from app.contexts.identity.domain.credentials import PASSWORD_MAX_LENGTH
from app.contexts.identity.infrastructure.login_attempts import RedisLoginAttempts
from app.contexts.identity.infrastructure.passwords import Argon2PasswordHasher
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.identity.infrastructure.verification_store import RedisChallengeStore
from app.contexts.identity.presentation.dependencies import SettingsDep, TokensDep
from app.contexts.identity.presentation.router import respond_with_tokens
from app.contexts.identity.presentation.schemas import AccessTokenResponse
from app.contexts.identity.presentation.signup_router import ClientIp
from app.core.clock import Clock
from app.core.dependencies import get_clock, get_mail_sender
from app.core.rate_limit import RedisRateLimiter
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailSender

router = APIRouter(prefix="/auth", tags=["auth"])

RedisDep = Annotated[Any, Depends(get_redis)]
ClockDep = Annotated[Clock, Depends(get_clock)]


async def get_password_login_service(
    redis: RedisDep, tokens: TokensDep, clock: ClockDep
) -> PasswordLoginService:
    hasher = Argon2PasswordHasher()
    return PasswordLoginService(
        users=TortoiseUserRepository(),
        hasher=hasher,
        attempts=RedisLoginAttempts(redis),
        tokens=tokens,
        uow=UnitOfWork(),
        clock=clock,
        dummy_hash=await dummy_hash(hasher),
    )


def get_password_reset_service(
    request: Request,
    settings: SettingsDep,
    redis: RedisDep,
    clock: ClockDep,
    mail: Annotated[MailSender, Depends(get_mail_sender)],
) -> PasswordResetService:
    return PasswordResetService(
        users=TortoiseUserRepository(),
        codes=VerificationCodes(
            challenges=RedisChallengeStore(redis),
            limiter=RedisRateLimiter(redis),
            clock=clock,
            secret=settings.jwt_secret_key.get_secret_value(),
        ),
        hasher=Argon2PasswordHasher(),
        attempts=RedisLoginAttempts(redis),
        mail=mail,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        sender_name=settings.mail_sender_name,
    )


Password = Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: Password


class ResetCodeRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)


class ResetRequest(ResetCodeRequest):
    code: str = Field(pattern=r"^\d{6}$")
    new_password: Password


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    settings: SettingsDep,
    service: Annotated[PasswordLoginService, Depends(get_password_login_service)],
) -> AccessTokenResponse:
    result = await service.login(body.email, body.password)
    return respond_with_tokens(response, result.tokens, settings)


@router.post("/password-reset/code", status_code=status.HTTP_204_NO_CONTENT)
async def request_reset_code(
    body: ResetCodeRequest,
    ip: ClientIp,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
) -> Response:
    await service.request_code(body.email, client_ip=ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    body: ResetRequest,
    service: Annotated[PasswordResetService, Depends(get_password_reset_service)],
) -> Response:
    await service.reset(body.email, body.code, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

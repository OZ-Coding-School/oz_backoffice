"""내 정보 비밀번호 변경 API (링크 인증, decisions A72).

GET  /me/password-change           → 상태 (내 정보 화면이 5초마다 확인)
POST /me/password-change/link      → 내 이메일로 인증 링크 (1분 간격·하루 5회)
POST /me/password-change           → 인증된 10분 안에 새 비밀번호 (204)
POST /auth/password-change/verify  → 메일 링크의 토큰 확인 (로그인 없이, 204)
"""

from datetime import datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import CurrentUser
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.application.password_change import (
    PasswordChangeService,
    PasswordChangeStatus,
)
from app.contexts.identity.domain.credentials import PASSWORD_MAX_LENGTH
from app.contexts.identity.domain.password_change import PasswordChangeState
from app.contexts.identity.infrastructure.login_attempts import RedisLoginAttempts
from app.contexts.identity.infrastructure.password_change_store import RedisPasswordChangeStore
from app.contexts.identity.infrastructure.passwords import Argon2PasswordHasher
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.identity.presentation.dependencies import SettingsDep
from app.core.clock import Clock
from app.core.dependencies import get_clock, get_mail_sender
from app.core.rate_limit import RedisRateLimiter
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailSender

me_router = APIRouter(prefix="/me/password-change", tags=["me"])
verify_router = APIRouter(prefix="/auth/password-change", tags=["auth"])


def get_password_change_service(
    request: Request,
    settings: SettingsDep,
    redis: Annotated[Any, Depends(get_redis)],
    clock: Annotated[Clock, Depends(get_clock)],
    mail: Annotated[MailSender, Depends(get_mail_sender)],
) -> PasswordChangeService:
    return PasswordChangeService(
        users=TortoiseUserRepository(),
        store=RedisPasswordChangeStore(redis),
        limiter=RedisRateLimiter(redis),
        hasher=Argon2PasswordHasher(),
        attempts=RedisLoginAttempts(redis),
        mail=mail,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        sender_name=settings.mail_sender_name,
        frontend_base_url=settings.frontend_base_url,
    )


ServiceDep = Annotated[PasswordChangeService, Depends(get_password_change_service)]


class PasswordChangeStatusResponse(BaseModel):
    available: bool = Field(description="비밀번호로 로그인하는 계정인지 (Google 전용이면 false)")
    state: PasswordChangeState = Field(description="NONE · SENT(링크 보냄) · VERIFIED(저장 가능)")
    expires_at: datetime | None = Field(description="SENT: 링크 만료, VERIFIED: 저장 마감")

    @classmethod
    def of(cls, s: PasswordChangeStatus) -> "PasswordChangeStatusResponse":
        return cls(available=s.available, state=s.state, expires_at=s.expires_at)


class PasswordChangeRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class PasswordLinkVerifyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@me_router.get("", response_model=PasswordChangeStatusResponse)
async def password_change_status(
    user: CurrentUser, service: ServiceDep
) -> PasswordChangeStatusResponse:
    return PasswordChangeStatusResponse.of(await service.status(user.id))


@me_router.post("/link", response_model=PasswordChangeStatusResponse)
async def send_password_change_link(
    user: CurrentUser, service: ServiceDep
) -> PasswordChangeStatusResponse:
    return PasswordChangeStatusResponse.of(await service.send_link(user.id))


@me_router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChangeRequest, user: CurrentUser, service: ServiceDep
) -> Response:
    await service.change(user.id, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@verify_router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_password_change_link(
    body: PasswordLinkVerifyRequest, service: ServiceDep
) -> Response:
    await service.verify(body.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

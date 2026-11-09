"""수강생·멘토 가입 API (인증 없음, decisions A30).

GET  /auth/signup/cohorts                → 가입 때 고를 수 있는 기수(활성 과정의 PLANNED·ONGOING)
POST /auth/signup/email-code             → gmail로 인증코드 발송
POST /auth/signup/email-code/verify      → 가입 토큰
POST /auth/signup/phone-code             → SMS 인증코드 발송 (가입 토큰)
POST /auth/signup/phone-code/verify
POST /auth/signup                        → 회원(PENDING) + 가입 신청 (토큰 없음, 다시 로그인)
"""

import uuid
from datetime import date
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.application.signup import MailDispatcher, SignupForm, SignupService
from app.contexts.identity.application.signup_matching import SignupMatcher
from app.contexts.identity.application.verification_codes import VerificationCodes
from app.contexts.identity.domain.credentials import PASSWORD_MAX_LENGTH
from app.contexts.identity.domain.enums import MemberSignupType, UserApprovalStatus
from app.contexts.identity.domain.verification import SIGNUP_SESSION_TTL
from app.contexts.identity.infrastructure.passwords import Argon2PasswordHasher
from app.contexts.identity.infrastructure.repositories import (
    TortoiseMemberSignupRepository,
    TortoiseUserRepository,
)
from app.contexts.identity.infrastructure.verification_store import (
    RedisChallengeStore,
    RedisSignupSessionStore,
)
from app.core.client_ip import resolve_client_ip
from app.core.clock import Clock
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_clock, get_mail_sender, get_sms_sender
from app.core.rate_limit import RedisRateLimiter
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailSender
from app.integrations.notifications.sms import SmsSender

router = APIRouter(prefix="/auth/signup", tags=["signup"])


def get_academy_catalog(request: Request) -> AcademyCatalog:
    return cast("AcademyCatalog", request.app.state.academy_catalog)


def get_signup_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    redis: Annotated[Any, Depends(get_redis)],
    clock: Annotated[Clock, Depends(get_clock)],
    mail: Annotated[MailSender, Depends(get_mail_sender)],
    sms: Annotated[SmsSender, Depends(get_sms_sender)],
    catalog: Annotated[AcademyCatalog, Depends(get_academy_catalog)],
) -> SignupService:
    return SignupService(
        users=TortoiseUserRepository(),
        signups=TortoiseMemberSignupRepository(),
        codes=VerificationCodes(
            challenges=RedisChallengeStore(redis),
            limiter=RedisRateLimiter(redis),
            clock=clock,
            secret=settings.jwt_secret_key.get_secret_value(),
        ),
        sessions=RedisSignupSessionStore(redis),
        hasher=Argon2PasswordHasher(),
        cohorts=catalog,
        matcher=cast("SignupMatcher", request.app.state.signup_matcher),
        mail=mail,
        mail_dispatcher=cast("MailDispatcher", request.app.state.mail_dispatcher),
        sms=sms,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        sender_name=settings.mail_sender_name,
        login_url=f"{settings.frontend_base_url.rstrip('/')}/login",
    )


def get_client_ip(
    request: Request, settings: Annotated[Settings, Depends(get_app_settings)]
) -> str:
    peer = request.client.host if request.client else None
    return resolve_client_ip(peer, request.headers.get("x-forwarded-for"), settings.trusted_proxies)


SignupDep = Annotated[SignupService, Depends(get_signup_service)]
ClientIp = Annotated[str, Depends(get_client_ip)]
Code = Annotated[str, Field(min_length=6, max_length=6, pattern=r"^\d{6}$")]


# ---------------------------------------------------------------- 스키마
class SignupCohortResponse(BaseModel):
    cohort_id: uuid.UUID
    bootcamp_id: uuid.UUID
    bootcamp_name: str
    cohort_number: int
    start_date: date
    end_date: date


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class EmailCodeVerifyRequest(EmailCodeRequest):
    code: Code


class SignupTokenResponse(BaseModel):
    signup_token: str
    expires_in: int = Field(description="가입 토큰 유효 시간(초)")


class PhoneCodeRequest(BaseModel):
    signup_token: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=10, max_length=20)


class PhoneCodeVerifyRequest(BaseModel):
    signup_token: str = Field(min_length=1, max_length=200)
    code: Code


class SignupRequest(BaseModel):
    signup_token: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    signup_type: MemberSignupType
    cohort_id: uuid.UUID | None = Field(default=None, description="수강생 필수")
    nickname: str | None = Field(default=None, max_length=30, description="멘토 선택")
    display_name_preference: DisplayNamePreference | None = Field(
        default=None, description="멘토 선택 (기본 NAME)"
    )


class SignupResponse(BaseModel):
    user_id: uuid.UUID
    signup_id: uuid.UUID
    signup_type: MemberSignupType
    approval_status: UserApprovalStatus


# ---------------------------------------------------------------- 엔드포인트
@router.get("/cohorts", response_model=list[SignupCohortResponse])
async def signup_cohorts(
    catalog: Annotated[AcademyCatalog, Depends(get_academy_catalog)],
) -> list[SignupCohortResponse]:
    bootcamps = {b.id: b for b in await catalog.staffable_bootcamps()}
    cohorts = sorted(
        await catalog.staffable_cohorts(),
        key=lambda c: (bootcamps[c.bootcamp_id].name, c.cohort_number),
    )
    return [
        SignupCohortResponse(
            cohort_id=c.id,
            bootcamp_id=c.bootcamp_id,
            bootcamp_name=bootcamps[c.bootcamp_id].name,
            cohort_number=c.cohort_number,
            start_date=c.start_date,
            end_date=c.end_date,
        )
        for c in cohorts
    ]


@router.post("/email-code", status_code=status.HTTP_204_NO_CONTENT)
async def request_email_code(body: EmailCodeRequest, signup: SignupDep, ip: ClientIp) -> Response:
    await signup.request_email_code(body.email, client_ip=ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/email-code/verify", response_model=SignupTokenResponse)
async def verify_email_code(body: EmailCodeVerifyRequest, signup: SignupDep) -> SignupTokenResponse:
    token = await signup.verify_email_code(body.email, body.code)
    return SignupTokenResponse(
        signup_token=token, expires_in=int(SIGNUP_SESSION_TTL.total_seconds())
    )


@router.post("/phone-code", status_code=status.HTTP_204_NO_CONTENT)
async def request_phone_code(body: PhoneCodeRequest, signup: SignupDep, ip: ClientIp) -> Response:
    await signup.request_phone_code(body.signup_token, body.phone_number, client_ip=ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/phone-code/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_phone_code(body: PhoneCodeVerifyRequest, signup: SignupDep) -> Response:
    await signup.verify_phone_code(body.signup_token, body.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def complete_signup(body: SignupRequest, signup: SignupDep) -> SignupResponse:
    result = await signup.complete(
        body.signup_token,
        SignupForm(
            name=body.name,
            password=body.password,
            signup_type=body.signup_type,
            cohort_id=body.cohort_id,
            nickname=body.nickname,
            display_name_preference=body.display_name_preference,
        ),
    )
    return SignupResponse(
        user_id=result.user.id,
        signup_id=result.signup.id,
        signup_type=result.signup.signup_type,
        approval_status=result.user.approval_status,
    )

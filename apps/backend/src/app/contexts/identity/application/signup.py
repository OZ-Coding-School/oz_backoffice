"""수강생·멘토 가입 (계획 P7, decisions A2·A3·A30).

① 이메일 인증: @gmail.com만 받는다. 이미 가입된 이메일은 409로 알린다. 6자리 코드를 메일로 보낸다.
② 코드 확인 → 가입 토큰(30분).
③ SMS 인증: 가입 토큰 + 휴대폰. 다른 계정에 등록된 번호는 거부한다. 코드를 문자로 보낸다.
④ 가입 완료: 가입 토큰 + 이름·비밀번호·유형(수강생은 기수, 멘토는 닉네임·표시 이름) →
   회원 + 가입 신청을 만들고 자동 매칭한다(A31). 일치하면 바로 승인하고 커밋 후 승인 알림
   메일을 워커로 보낸다. 아니면 승인 대기(PENDING). 토큰은 주지 않는다(다시 로그인, A30).

코드 발급·검증·발송 제한은 `VerificationCodes`(IP당 횟수는 메일·SMS 합산). 발송은 요청 안에서
바로 하고 실패하면 503으로 알린다(A29).
"""

import secrets
import uuid
from dataclasses import dataclass, replace
from typing import Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.application.signup_mails import approval_mail
from app.contexts.identity.application.signup_matching import SignupMatcher
from app.contexts.identity.application.verification_codes import VerificationCodes, seconds
from app.contexts.identity.domain.credentials import validate_password
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType, MemberSignupType, SignupMatchResult
from app.contexts.identity.domain.repositories import MemberSignupRepository, UserRepository
from app.contexts.identity.domain.signup import MemberSignup
from app.contexts.identity.domain.verification import (
    SIGNUP_SESSION_TTL,
    ChallengeKind,
    SignupSession,
    SignupSessionStore,
)
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailMessage, MailSender
from app.integrations.notifications.sms import SmsMessage, SmsSender
from app.shared.errors import BusinessRuleViolation, ConflictError
from app.shared.normalization import normalize_phone
from app.shared.value_objects import Email

ALLOWED_EMAIL_DOMAIN = "gmail.com"
SIGNUP_IP_LIMIT = "signup_ip"  # 가입 메일·SMS 발송을 IP당 합산


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...


class SignupCohorts(Protocol):
    """academy 공개 조회 (`AcademyCatalog`). 가입 때 고를 수 있는 기수인지."""

    async def is_signup_cohort(self, cohort_id: uuid.UUID) -> bool: ...


class MailDispatcher(Protocol):
    """알림 메일을 커밋 후 워커로 보낸다 (`TaskiqMailDispatcher`)."""

    async def dispatch(self, message: MailMessage) -> None: ...


async def settle_auto_match(
    *,
    matcher: SignupMatcher,
    user: User,
    signup: MemberSignup,
    users: UserRepository,
    uow: UnitOfWork,
    dispatcher: MailDispatcher,
    clock: Clock,
    sender_name: str,
    login_url: str,
) -> SignupMatchResult:
    """자동 매칭하고 일치하면 회원·신청을 승인한다(A31). 커밋 후 승인 메일을 보낸다.

    가입 완료와 재신청이 함께 쓴다. 호출하는 쪽의 트랜잭션 안에서 실행한다.
    """
    result = await matcher.match(user, signup)
    signup.record_match(result)
    if result is SignupMatchResult.MATCHED:
        now = clock.now()
        user.approve(now=now)
        signup.approve(now=now)
        await users.save(user)
        message = approval_mail(user, sender_name=sender_name, login_url=login_url)
        uow.on_commit(lambda: dispatcher.dispatch(message))
    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class SignupForm:
    name: str
    password: str
    signup_type: MemberSignupType
    cohort_id: uuid.UUID | None = None
    nickname: str | None = None
    display_name_preference: DisplayNamePreference | None = None


@dataclass(frozen=True, slots=True)
class SignupResult:
    user: User
    signup: MemberSignup


class SignupService:
    def __init__(
        self,
        *,
        users: UserRepository,
        signups: MemberSignupRepository,
        codes: VerificationCodes,
        sessions: SignupSessionStore,
        hasher: PasswordHasher,
        cohorts: SignupCohorts,
        matcher: SignupMatcher,
        mail: MailSender,
        mail_dispatcher: MailDispatcher,
        sms: SmsSender,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        sender_name: str,
        login_url: str,
    ) -> None:
        self._users = users
        self._signups = signups
        self._codes = codes
        self._sessions = sessions
        self._hasher = hasher
        self._cohorts = cohorts
        self._matcher = matcher
        self._mail = mail
        self._dispatcher = mail_dispatcher
        self._sms = sms
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._sender_name = sender_name
        self._login_url = login_url

    # ------------------------------------------------------------------ ① ② 이메일
    async def request_email_code(self, raw_email: str, *, client_ip: str) -> None:
        email = self._signup_email(raw_email)
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("이미 가입된 이메일입니다.", code="email_already_registered")
        await self._codes.prepare(
            ChallengeKind.SIGNUP_EMAIL,
            email,
            limit_name="signup_email",
            subject=email,
            ip_limit_name=SIGNUP_IP_LIMIT,
            client_ip=client_ip,
        )
        code = await self._codes.issue(ChallengeKind.SIGNUP_EMAIL, email, target=email)
        await self._codes.deliver(
            ChallengeKind.SIGNUP_EMAIL,
            email,
            self._mail.send(
                MailMessage(
                    to=email,
                    subject=f"[{self._sender_name}] 이메일 인증코드 {code}",
                    text=(
                        f"{self._sender_name} 회원가입 이메일 인증코드는 {code} 입니다.\n"
                        "10분 이내에 입력해 주세요. 요청하지 않았다면 이 메일을 무시하세요."
                    ),
                    html=(
                        f"<p>{self._sender_name} 회원가입 이메일 인증코드</p>"
                        f'<p style="font-size:24px;font-weight:bold;letter-spacing:4px">{code}</p>'
                        "<p>10분 이내에 입력해 주세요. 요청하지 않았다면 이 메일을 무시하세요.</p>"
                    ),
                )
            ),
        )

    async def verify_email_code(self, raw_email: str, code: str) -> str:
        """코드가 맞으면 가입 토큰(30분)을 돌려준다."""
        email = self._signup_email(raw_email)
        await self._codes.verify(ChallengeKind.SIGNUP_EMAIL, email, code)
        now = self._clock.now()
        token = secrets.token_urlsafe(32)
        session = SignupSession(
            email=email, email_verified_at=now, expires_at=now + SIGNUP_SESSION_TTL
        )
        await self._sessions.put(
            token, session, ttl_seconds=seconds(SIGNUP_SESSION_TTL.total_seconds())
        )
        return token

    # ------------------------------------------------------------------ ③ 휴대폰
    async def request_phone_code(self, token: str, raw_phone: str, *, client_ip: str) -> None:
        await self._session(token)
        phone = normalize_phone(raw_phone)
        await self._ensure_phone_free(phone)
        await self._codes.prepare(
            ChallengeKind.SIGNUP_PHONE,
            token,
            limit_name="signup_phone",
            subject=phone,
            ip_limit_name=SIGNUP_IP_LIMIT,
            client_ip=client_ip,
        )
        code = await self._codes.issue(ChallengeKind.SIGNUP_PHONE, token, target=phone)
        await self._codes.deliver(
            ChallengeKind.SIGNUP_PHONE,
            token,
            self._sms.send(
                SmsMessage(to=phone, text=f"[{self._sender_name}] 인증번호 {code} (10분 이내 입력)")
            ),
        )

    async def verify_phone_code(self, token: str, code: str) -> None:
        session = await self._session(token)
        challenge = await self._codes.verify(ChallengeKind.SIGNUP_PHONE, token, code)
        verified = replace(
            session, phone_number=challenge.target, phone_verified_at=self._clock.now()
        )
        await self._sessions.put(
            token,
            verified,
            ttl_seconds=seconds((session.expires_at - self._clock.now()).total_seconds()),
        )

    # ------------------------------------------------------------------ ④ 가입 완료
    async def complete(self, token: str, form: SignupForm) -> SignupResult:
        session = await self._session(token)
        if not session.is_complete or session.phone_number is None:
            raise BusinessRuleViolation(
                "휴대폰 인증을 먼저 완료하세요.", code="phone_verification_required"
            )
        validate_password(form.password)
        if form.signup_type is MemberSignupType.STUDENT and (
            form.cohort_id is None or not await self._cohorts.is_signup_cohort(form.cohort_id)
        ):
            raise BusinessRuleViolation("가입할 수 있는 기수를 선택하세요.", code="invalid_cohort")
        user = User(
            email=session.email,
            name=form.name,
            account_type=AccountType.MEMBER,
            hashed_password=await self._hasher.hash(form.password),
            phone_number=session.phone_number,
            email_verified_at=session.email_verified_at,
            phone_verified_at=session.phone_verified_at,
        )
        signup = MemberSignup(
            user_id=user.id,
            signup_type=form.signup_type,
            requested_cohort_id=form.cohort_id
            if form.signup_type is MemberSignupType.STUDENT
            else None,
            nickname=form.nickname if form.signup_type is MemberSignupType.MENTOR else None,
            display_name_preference=form.display_name_preference
            if form.signup_type is MemberSignupType.MENTOR
            else None,
        )
        async with self._uow:
            # 인증 이후 다른 요청이 같은 이메일·휴대폰으로 먼저 가입했을 수 있다
            if await self._users.get_by_email(user.email) is not None:
                raise ConflictError("이미 가입된 이메일입니다.", code="email_already_registered")
            await self._ensure_phone_free(session.phone_number)
            await self._users.add(user)
            # 자동 매칭 (A6·A31): 일치하면 바로 승인, 아니면 승인 대기
            result = await settle_auto_match(
                matcher=self._matcher,
                user=user,
                signup=signup,
                users=self._users,
                uow=self._uow,
                dispatcher=self._dispatcher,
                clock=self._clock,
                sender_name=self._sender_name,
                login_url=self._login_url,
            )
            await self._signups.add(signup)
            await self._audit.record(
                actor_user_id=user.id,
                action="identity.member_signup.create",
                target_type="member_signup",
                target_id=signup.id,
                after={
                    "signup_type": signup.signup_type.value,
                    "match_result": result.value,
                    "status": signup.status.value,
                },
            )
        await self._sessions.delete(token)
        return SignupResult(user=user, signup=signup)

    # ------------------------------------------------------------------ 내부
    def _signup_email(self, raw: str) -> str:
        try:
            email = Email(raw)
        except ValueError as exc:
            raise BusinessRuleViolation(
                "이메일 형식이 올바르지 않습니다.", code="invalid_email"
            ) from exc
        if email.domain != ALLOWED_EMAIL_DOMAIN:
            raise BusinessRuleViolation(
                "Gmail(@gmail.com) 주소로만 가입할 수 있습니다.", code="email_domain_not_allowed"
            )
        return email.value

    async def _session(self, token: str) -> SignupSession:
        session = await self._sessions.get(token) if token else None
        if session is None:
            raise BusinessRuleViolation(
                "가입 시간이 지났습니다. 이메일 인증부터 다시 진행하세요.",
                code="signup_session_expired",
            )
        return session

    async def _ensure_phone_free(self, phone: str) -> None:
        if await self._users.get_by_phone(phone) is not None:
            raise ConflictError(
                "다른 계정에 등록된 휴대폰 번호입니다.", code="phone_already_registered"
            )

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.application.signup import SignupForm, SignupService
from app.contexts.identity.domain.enums import (
    MemberSignupStatus,
    MemberSignupType,
    UserApprovalStatus,
)
from app.contexts.identity.infrastructure.verification_store import (
    RedisChallengeStore,
    RedisSignupSessionStore,
)
from app.core.clock import FixedClock
from app.core.rate_limit import RedisRateLimiter
from app.integrations.notifications.mail import MailDeliveryError, MailMessage
from app.shared.errors import BusinessRuleViolation, ConflictError, TooManyRequestsError
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.identity import InMemoryMemberSignupRepository, InMemoryUserRepository
from tests.fakes.notifications import InMemoryMailSender, InMemorySmsSender
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)
EMAIL = "kim@gmail.com"
PHONE = "01012345678"
IP = "1.2.3.4"


class FakeHasher:
    async def hash(self, password: str) -> str:
        return f"hashed:{password}"


class FakeCohorts:
    def __init__(self, *open_ids: uuid.UUID) -> None:
        self.open = set(open_ids)

    async def is_signup_cohort(self, cohort_id: uuid.UUID) -> bool:
        return cohort_id in self.open


class FailingMail:
    async def send(self, message: MailMessage) -> None:
        raise MailDeliveryError("실패")


class Harness:
    def __init__(self, redis: FakeAsyncRedis) -> None:
        self.clock = FixedClock(NOW)
        self.users = InMemoryUserRepository()
        self.signups = InMemoryMemberSignupRepository()
        self.mail = InMemoryMailSender()
        self.sms = InMemorySmsSender()
        self.cohort_id = new_id()
        self.audit_logs = InMemoryAuditLogRepository()
        self.challenges = RedisChallengeStore(redis)
        self.service = SignupService(
            users=self.users,
            signups=self.signups,
            challenges=self.challenges,
            sessions=RedisSignupSessionStore(redis),
            limiter=RedisRateLimiter(redis),
            hasher=FakeHasher(),
            cohorts=FakeCohorts(self.cohort_id),
            mail=self.mail,
            sms=self.sms,
            audit=AuditRecorder(self.audit_logs, self.clock),
            uow=FakeUnitOfWork(),
            clock=self.clock,
            code_secret="secret",
            sender_name="오즈코딩스쿨",
        )

    def last_mail_code(self) -> str:
        match = re.search(r"\b(\d{6})\b", self.mail.sent[-1].text)
        assert match
        return match.group(1)

    def last_sms_code(self) -> str:
        match = re.search(r"인증번호 (\d{6})", self.sms.sent[-1].text)
        assert match
        return match.group(1)

    async def verified_token(self) -> str:
        await self.service.request_email_code(EMAIL, client_ip=IP)
        token = await self.service.verify_email_code(EMAIL, self.last_mail_code())
        self.clock.set(self.clock.now() + timedelta(seconds=1))
        await self.service.request_phone_code(token, "010-1234-5678", client_ip=IP)
        await self.service.verify_phone_code(token, self.last_sms_code())
        return token

    def form(self, **overrides: object) -> SignupForm:
        values: dict[str, object] = {
            "name": "김수강",
            "password": "abcd123!",
            "signup_type": MemberSignupType.STUDENT,
            "cohort_id": self.cohort_id,
        }
        values.update(overrides)
        return SignupForm(**values)  # type: ignore[arg-type]  # 테스트 입력


@pytest.fixture
def h(fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(fake_redis)


async def test_full_signup_creates_pending_user_and_signup(h: Harness) -> None:
    token = await h.verified_token()

    result = await h.service.complete(token, h.form())

    user = result.user
    assert (user.email, user.phone_number, user.hashed_password) == (
        EMAIL,
        PHONE,
        "hashed:abcd123!",
    )
    assert user.approval_status is UserApprovalStatus.PENDING
    assert user.email_verified_at == NOW
    assert user.phone_verified_at is not None
    signup = result.signup
    assert (signup.signup_type, signup.requested_cohort_id, signup.status) == (
        MemberSignupType.STUDENT,
        h.cohort_id,
        MemberSignupStatus.PENDING,
    )
    assert h.mail.sent[0].subject == f"[오즈코딩스쿨] 이메일 인증코드 {h.last_mail_code()}"
    assert h.sms.sent[0].text.startswith("[오즈코딩스쿨] 인증번호 ")
    assert h.audit_logs.logs[-1].action == "identity.member_signup.create"
    with pytest.raises(BusinessRuleViolation) as reused:  # 토큰은 한 번만
        await h.service.complete(token, h.form())
    assert reused.value.code == "signup_session_expired"


async def test_mentor_signup_fields(h: Harness) -> None:
    token = await h.verified_token()
    result = await h.service.complete(
        token,
        h.form(
            signup_type=MemberSignupType.MENTOR,
            cohort_id=h.cohort_id,  # 멘토는 기수를 무시한다
            nickname="오즈",
            display_name_preference=DisplayNamePreference.NICKNAME,
        ),
    )
    assert result.signup.requested_cohort_id is None
    assert result.signup.nickname == "오즈"


@pytest.mark.parametrize(
    ("email", "code"),
    [("kim@naver.com", "email_domain_not_allowed"), ("not-email", "invalid_email")],
)
async def test_only_gmail(h: Harness, email: str, code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.service.request_email_code(email, client_ip=IP)
    assert exc.value.code == code


async def test_registered_email_and_phone_are_rejected(h: Harness) -> None:
    await h.users.add(make_user(email=EMAIL))
    with pytest.raises(ConflictError) as email:
        await h.service.request_email_code(EMAIL, client_ip=IP)
    assert email.value.code == "email_already_registered"

    await h.service.request_email_code("lee@gmail.com", client_ip=IP)
    token = await h.service.verify_email_code("lee@gmail.com", h.last_mail_code())
    await h.users.add(make_user(email="other@gmail.com", phone_number=PHONE))
    with pytest.raises(ConflictError) as phone:
        await h.service.request_phone_code(token, PHONE, client_ip=IP)
    assert phone.value.code == "phone_already_registered"


async def test_code_attempts_and_expiry(h: Harness) -> None:
    await h.service.request_email_code(EMAIL, client_ip=IP)
    code = h.last_mail_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        with pytest.raises(BusinessRuleViolation) as exc:
            await h.service.verify_email_code(EMAIL, wrong)
        assert exc.value.code == "invalid_verification_code"
    with pytest.raises(BusinessRuleViolation):  # 5번째 실패로 코드가 폐기된다
        await h.service.verify_email_code(EMAIL, wrong)
    with pytest.raises(BusinessRuleViolation) as gone:
        await h.service.verify_email_code(EMAIL, code)
    assert gone.value.code == "verification_code_expired"

    h.clock.set(NOW + timedelta(minutes=2))
    await h.service.request_email_code(EMAIL, client_ip=IP)
    h.clock.set(NOW + timedelta(minutes=12, seconds=1))  # 10분 경과
    with pytest.raises(BusinessRuleViolation) as expired:
        await h.service.verify_email_code(EMAIL, h.last_mail_code())
    assert expired.value.code == "verification_code_expired"


async def test_resend_interval_and_rate_limit(h: Harness) -> None:
    await h.service.request_email_code(EMAIL, client_ip=IP)
    with pytest.raises(TooManyRequestsError) as soon:
        await h.service.request_email_code(EMAIL, client_ip=IP)
    assert (soon.value.code, soon.value.retry_after) == ("resend_too_soon", 60)

    for minute in range(1, 5):  # 대상당 1시간 5회
        h.clock.set(NOW + timedelta(minutes=minute))
        await h.service.request_email_code(EMAIL, client_ip=IP)
    h.clock.set(NOW + timedelta(minutes=6))
    with pytest.raises(TooManyRequestsError) as limited:
        await h.service.request_email_code(EMAIL, client_ip=IP)
    assert limited.value.code == "rate_limited"


async def test_ip_limit_counts_all_targets(h: Harness) -> None:
    for n in range(20):
        await h.service.request_email_code(f"user{n}@gmail.com", client_ip=IP)
    with pytest.raises(TooManyRequestsError):
        await h.service.request_email_code("user99@gmail.com", client_ip=IP)
    await h.service.request_email_code("user99@gmail.com", client_ip="5.6.7.8")


async def test_failed_delivery_discards_code(h: Harness) -> None:
    h.service._mail = FailingMail()  # 발송 실패 주입
    with pytest.raises(MailDeliveryError):
        await h.service.request_email_code(EMAIL, client_ip=IP)
    from app.contexts.identity.domain.verification import ChallengeKind

    assert await h.challenges.get(ChallengeKind.SIGNUP_EMAIL, EMAIL) is None


async def test_complete_validations(h: Harness) -> None:
    await h.service.request_email_code(EMAIL, client_ip=IP)
    token = await h.service.verify_email_code(EMAIL, h.last_mail_code())
    with pytest.raises(BusinessRuleViolation) as phone:
        await h.service.complete(token, h.form())
    assert phone.value.code == "phone_verification_required"

    h.clock.set(NOW + timedelta(seconds=1))
    await h.service.request_phone_code(token, PHONE, client_ip=IP)
    await h.service.verify_phone_code(token, h.last_sms_code())
    for form, code in (
        (h.form(password="weakpass"), "invalid_password"),
        (h.form(cohort_id=new_id()), "invalid_cohort"),
        (h.form(cohort_id=None), "invalid_cohort"),
    ):
        with pytest.raises(BusinessRuleViolation) as exc:
            await h.service.complete(token, form)
        assert exc.value.code == code
    with pytest.raises(BusinessRuleViolation) as missing:
        await h.service.request_phone_code("unknown-token", PHONE, client_ip=IP)
    assert missing.value.code == "signup_session_expired"

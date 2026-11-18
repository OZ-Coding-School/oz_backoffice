"""identity 도메인 엔티티."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime

from app.contexts.identity.domain.enums import AccountType, SocialLoginProvider, UserApprovalStatus
from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation
from app.shared.normalization import normalize_name, normalize_phone
from app.shared.value_objects import Email


@dataclass(kw_only=True, eq=False)
class User(AggregateRoot):
    """회원 (운영진·멘토·강사·수강생 공통).

    - email은 소문자로 정규화한다 (users.email check 제약).
    - 승인 상태: PENDING → APPROVED | REJECTED, REJECTED → APPROVED(재승인) | PENDING(재신청).
    """

    email: str
    name: str
    account_type: AccountType
    hashed_password: str | None = None
    phone_number: str | None = None
    birth_date: date | None = None
    approval_status: UserApprovalStatus = UserApprovalStatus.PENDING
    approved_at: datetime | None = None
    email_verified_at: datetime | None = None
    phone_verified_at: datetime | None = None
    is_active: bool = False
    last_login_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        try:
            self.email = Email(self.email).value
        except ValueError as exc:
            raise BusinessRuleViolation(
                "이메일 형식이 올바르지 않습니다.", code="invalid_email"
            ) from exc
        self.name = normalize_name(self.name)
        if self.phone_number is not None:
            self.phone_number = normalize_phone(self.phone_number)
        if (self.approval_status is UserApprovalStatus.APPROVED) != (self.approved_at is not None):
            raise BusinessRuleViolation(
                "승인 상태와 승인 시각이 일치하지 않습니다.", code="invalid_approval_state"
            )

    @property
    def is_approved(self) -> bool:
        return self.approval_status is UserApprovalStatus.APPROVED

    @property
    def can_login(self) -> bool:
        """탈퇴했거나, 승인 후 비활성화(정지)된 계정은 로그인할 수 없다.

        승인 전(PENDING·REJECTED)에는 is_active가 false여도 로그인해
        상태를 볼 수 있다 (§2.2 게이트).
        """
        if self.deleted_at is not None:
            return False
        return self.is_active or not self.is_approved

    def approve(self, *, now: datetime) -> None:
        if self.approval_status is UserApprovalStatus.APPROVED:
            raise BusinessRuleViolation("이미 승인된 회원입니다.", code="user_already_approved")
        self.approval_status = UserApprovalStatus.APPROVED
        self.approved_at = now
        self.is_active = True

    def reject(self) -> None:
        if self.approval_status is not UserApprovalStatus.PENDING:
            raise BusinessRuleViolation(
                "승인 대기 중인 회원만 반려할 수 있습니다.", code="user_not_pending"
            )
        self.approval_status = UserApprovalStatus.REJECTED

    def resubmit(self) -> None:
        """반려된 회원이 다시 신청한다: REJECTED → PENDING (decisions A30·A33)."""
        if self.approval_status is not UserApprovalStatus.REJECTED:
            raise BusinessRuleViolation(
                "반려된 회원만 다시 신청할 수 있습니다.", code="user_not_rejected"
            )
        self.approval_status = UserApprovalStatus.PENDING

    def change_member_type(self, account_type: AccountType) -> None:
        """승인 전 회원이 다른 유형으로 다시 신청하면 계정 종류도 바꾼다 (A65).

        승인된 계정·운영진 계정은 바꿀 수 없다(한 계정은 수강생·멘토 중 하나).
        """
        members = (AccountType.STUDENT, AccountType.MENTOR)
        if self.is_approved or self.account_type not in members or account_type not in members:
            raise BusinessRuleViolation("계정 종류를 바꿀 수 없습니다.", code="account_type_locked")
        self.account_type = account_type

    def verify_email(self, *, now: datetime) -> None:
        self.email_verified_at = now

    def verify_phone(self, phone_number: str, *, now: datetime) -> None:
        self.phone_number = normalize_phone(phone_number)
        self.phone_verified_at = now

    def change_password(self, hashed_password: str) -> None:
        """새 비밀번호 해시로 바꾼다(재설정, 다시 해시). 비밀번호 규칙은 해시 전에 검사한다."""
        self.hashed_password = hashed_password

    def record_login(self, *, now: datetime) -> None:
        self.last_login_at = now

    def deactivate(self) -> None:
        self.is_active = False


@dataclass(kw_only=True, eq=False)
class OAuthAccount(Entity):
    """소셜 로그인 연결 (운영진 Google 로그인 등). (provider, provider_user_id)는 유일하다."""

    user_id: uuid.UUID
    provider: SocialLoginProvider
    provider_user_id: str = field()

    def __post_init__(self) -> None:
        if not self.provider_user_id:
            raise BusinessRuleViolation(
                "소셜 계정 ID가 비어 있습니다.", code="invalid_oauth_account"
            )

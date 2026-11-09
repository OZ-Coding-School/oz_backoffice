"""수강생·멘토 가입 신청 (decisions A30).

- 수강생은 신청 기수가 필수, 멘토는 기수가 없고 닉네임·표시 이름을 선택 입력한다.
- 상태: PENDING → APPROVED | REJECTED. 반려되면 새 신청으로 다시 신청한다(이력 보존).
- 회원당 대기 신청은 하나다(DB 부분 유니크).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.enums import (
    MemberSignupStatus,
    MemberSignupType,
    SignupMatchResult,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

NICKNAME_MAX_LENGTH = 30
REJECT_REASON_MAX_LENGTH = 300


@dataclass(kw_only=True, eq=False)
class MemberSignup(AggregateRoot):
    user_id: uuid.UUID
    signup_type: MemberSignupType
    requested_cohort_id: uuid.UUID | None = None
    nickname: str | None = None
    display_name_preference: DisplayNamePreference | None = None
    match_result: SignupMatchResult | None = None
    status: MemberSignupStatus = MemberSignupStatus.PENDING
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.signup_type is MemberSignupType.STUDENT:
            if self.requested_cohort_id is None:
                raise BusinessRuleViolation("수강 중인 기수를 선택하세요.", code="cohort_required")
            if self.nickname is not None or self.display_name_preference is not None:
                raise BusinessRuleViolation(
                    "닉네임·표시 이름은 멘토만 입력합니다.", code="invalid_signup_field"
                )
            return
        if self.requested_cohort_id is not None:
            raise BusinessRuleViolation(
                "멘토는 기수를 선택하지 않습니다.", code="invalid_signup_field"
            )
        nickname = (self.nickname or "").strip()
        if len(nickname) > NICKNAME_MAX_LENGTH:
            raise BusinessRuleViolation(
                f"닉네임은 {NICKNAME_MAX_LENGTH}자 이하여야 합니다.", code="invalid_nickname"
            )
        self.nickname = nickname or None
        if self.display_name_preference is None:
            self.display_name_preference = DisplayNamePreference.NAME
        if self.display_name_preference is DisplayNamePreference.NICKNAME and not self.nickname:
            raise BusinessRuleViolation(
                "닉네임을 입력해야 닉네임으로 표시할 수 있습니다.", code="nickname_required"
            )

    @property
    def is_pending(self) -> bool:
        return self.status is MemberSignupStatus.PENDING

    def approve(self, *, now: datetime) -> None:
        self._ensure_pending()
        self.status = MemberSignupStatus.APPROVED
        self.reviewed_at = now

    def reject(self, reason: str, *, now: datetime) -> None:
        self._ensure_pending()
        text = reason.strip()
        if not text or len(text) > REJECT_REASON_MAX_LENGTH:
            raise BusinessRuleViolation(
                f"반려 사유는 1~{REJECT_REASON_MAX_LENGTH}자여야 합니다.",
                code="invalid_reject_reason",
            )
        self.status = MemberSignupStatus.REJECTED
        self.reviewed_at = now
        self.reject_reason = text

    def _ensure_pending(self) -> None:
        if not self.is_pending:
            raise BusinessRuleViolation(
                "승인 대기 중인 신청만 처리할 수 있습니다.", code="signup_not_pending"
            )

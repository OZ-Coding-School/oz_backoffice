"""멘토링 시간 계좌와 원장 (decisions M8·M9·M10·A39·A40).

- 계좌는 수강생(수강 등록) 또는 팀당 하나이고(유형 구분 없음, A41),
  사용 기간(valid_from~valid_until)이 있다.
- 잔여 = 지급 합계 − 보류 − 사용, 음수 불가.
- 운영진 지급·조정은 60분 단위, 사유 필수(100자). 사용 기간이 끝난 계좌에는 지급·늘리는 조정을
  하지 않고 줄이는 조정만 한다.
- 사용 기간은 기수 기간 안이어야 한다.
- 원장(append-only)은 계좌 변경마다 한 줄씩 남기고, 변경 후 잔여·보류를 함께 적는다.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType
from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation

GRANT_UNIT_MINUTES = 60
REASON_MAX_LENGTH = 100


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def clean_reason(reason: str) -> str:
    text = reason.strip()
    _rule(
        0 < len(text) <= REASON_MAX_LENGTH,
        f"사유를 1~{REASON_MAX_LENGTH}자로 적어 주세요.",
        "invalid_balance_reason",
    )
    return text


def ensure_grant_minutes(minutes: int) -> None:
    _rule(
        minutes > 0 and minutes % GRANT_UNIT_MINUTES == 0,
        "지급 시간은 60분 단위의 양수입니다.",
        "invalid_balance_minutes",
    )


def ensure_validity(
    valid_from: date, valid_until: date, *, cohort_start: date, cohort_end: date
) -> None:
    _rule(
        valid_from <= valid_until,
        "사용 기간의 시작일이 종료일보다 늦습니다.",
        "invalid_balance_validity",
    )
    _rule(
        cohort_start <= valid_from and valid_until <= cohort_end,
        "사용 기간은 기수 기간 안이어야 합니다.",
        "balance_validity_outside_cohort",
    )


@dataclass(kw_only=True, eq=False)
class BalanceTransaction(Entity):
    account_id: uuid.UUID
    type: MentoringBalanceTransactionType
    amount: int
    after_remaining: int
    after_held: int
    reason: str
    request_id: uuid.UUID | None = None
    created_at: datetime | None = None


@dataclass(kw_only=True, eq=False)
class BalanceAccount(AggregateRoot):
    valid_from: date
    valid_until: date
    student_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    total_minutes: int = 0
    held_minutes: int = 0
    used_minutes: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _rule(
            (self.student_id is None) != (self.team_id is None),
            "계좌 소유자는 수강생 또는 팀 하나입니다.",
            "invalid_balance_owner",
        )
        _rule(
            self.valid_from <= self.valid_until,
            "사용 기간의 시작일이 종료일보다 늦습니다.",
            "invalid_balance_validity",
        )

    @property
    def remaining_minutes(self) -> int:
        return self.total_minutes - self.held_minutes - self.used_minutes

    def is_expired(self, today: date) -> bool:
        return self.valid_until < today

    def grant(self, minutes: int, reason: str, *, today: date) -> BalanceTransaction:
        ensure_grant_minutes(minutes)
        _rule(
            not self.is_expired(today),
            "사용 기간이 끝난 계좌입니다. 기간을 먼저 연장하세요.",
            "balance_account_expired",
        )
        self.total_minutes += minutes
        return self._entry(MentoringBalanceTransactionType.STAFF_GRANT, minutes, reason)

    def adjust(self, delta: int, reason: str, *, today: date) -> BalanceTransaction:
        _rule(
            delta != 0 and delta % GRANT_UNIT_MINUTES == 0,
            "조정 시간은 60분 단위이고 0이 아니어야 합니다.",
            "invalid_balance_minutes",
        )
        _rule(
            delta < 0 or not self.is_expired(today),
            "사용 기간이 끝난 계좌는 줄이는 조정만 할 수 있습니다.",
            "balance_account_expired",
        )
        _rule(
            self.remaining_minutes + delta >= 0,
            "잔여 시간보다 많이 줄일 수 없습니다.",
            "insufficient_balance",
        )
        self.total_minutes += delta
        return self._entry(MentoringBalanceTransactionType.STAFF_ADJUST, delta, reason)

    def hold(self, minutes: int, *, request_id: uuid.UUID, reason: str) -> BalanceTransaction:
        """신청: 잔여에서 보류로 옮긴다 (M9)."""
        _rule(minutes > 0, "보류 시간이 올바르지 않습니다.", "invalid_balance_minutes")
        _rule(self.remaining_minutes >= minutes, "잔여 시간이 부족합니다.", "insufficient_balance")
        self.held_minutes += minutes
        return self._entry(MentoringBalanceTransactionType.HOLD, minutes, reason, request_id)

    def release(self, minutes: int, *, request_id: uuid.UUID, reason: str) -> BalanceTransaction:
        """승인 전 반려·취소·만료: 보류를 잔여로 돌린다 (M9)."""
        _rule(
            0 < minutes <= self.held_minutes,
            "해제할 보류 시간이 없습니다.",
            "invalid_balance_minutes",
        )
        self.held_minutes -= minutes
        return self._entry(MentoringBalanceTransactionType.RELEASE, minutes, reason, request_id)

    def use(self, minutes: int, *, request_id: uuid.UUID, reason: str) -> BalanceTransaction:
        """승인: 보류를 사용으로 옮긴다 (M9)."""
        _rule(
            0 < minutes <= self.held_minutes,
            "사용할 보류 시간이 없습니다.",
            "invalid_balance_minutes",
        )
        self.held_minutes -= minutes
        self.used_minutes += minutes
        return self._entry(MentoringBalanceTransactionType.USING, minutes, reason, request_id)

    def refund(self, minutes: int, *, request_id: uuid.UUID, reason: str) -> BalanceTransaction:
        """승인 후 취소: 사용을 잔여로 돌린다 (M9·M26)."""
        _rule(
            0 < minutes <= self.used_minutes,
            "환불할 사용 시간이 없습니다.",
            "invalid_balance_minutes",
        )
        self.used_minutes -= minutes
        return self._entry(MentoringBalanceTransactionType.REFUND, minutes, reason, request_id)

    def revoke_remaining(self, reason: str) -> BalanceTransaction | None:
        """수강 종료 회수: 잔여 전부를 줄인다(단위·사용 기간과 무관, A39). 잔여가 없으면 None."""
        if self.remaining_minutes <= 0:
            return None
        delta = -self.remaining_minutes
        self.total_minutes += delta
        return self._entry(MentoringBalanceTransactionType.STAFF_ADJUST, delta, reason)

    def change_validity(
        self, valid_from: date, valid_until: date, *, cohort_start: date, cohort_end: date
    ) -> None:
        ensure_validity(valid_from, valid_until, cohort_start=cohort_start, cohort_end=cohort_end)
        self.valid_from = valid_from
        self.valid_until = valid_until

    def _entry(
        self,
        type_: MentoringBalanceTransactionType,
        amount: int,
        reason: str,
        request_id: uuid.UUID | None = None,
    ) -> BalanceTransaction:
        return BalanceTransaction(
            account_id=self.id,
            type=type_,
            amount=amount,
            after_remaining=self.remaining_minutes,
            after_held=self.held_minutes,
            reason=clean_reason(reason),
            request_id=request_id,
        )

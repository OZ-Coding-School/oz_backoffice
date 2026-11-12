"""멘토링 신청 (decisions M1·M3·M5·M9·A41·A42).

- 수강생 본인만 신청한다(대리 신청 없음). 팀 신청은 팀원 누구나, 취소·변경은 신청자만.
- 희망 일시 1~3개, 각각 30분 경계, 서로 겹치지 않는다. 신청 시간은 진행 단위의 배수, 최대 120분.
- 주제 100자, 상세 내용 필수 2,000자. 반려·취소 사유 필수 300자.
- 상태: PENDING → APPROVED / REJECTED / CANCELED, APPROVED → CANCELED (승인 후 취소, M26).
- 승인은 고른 희망 일시가 시작하기 전까지, 반려는 대기 중일 때 사유와 함께 (A42·A43).
- 승인 가능한 희망 일시(시작 전)가 하나도 없으면 대기 만료 대상이다.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.contexts.mentoring.domain.enums import MentoringRequestStatus
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation
from app.shared.time import KST

MAX_DESIRED = 3
MAX_DURATION_MINUTES = 120
SLOT_MINUTES = 30
TOPIC_MAX_LENGTH = 100
DETAIL_MAX_LENGTH = 2000
REASON_MAX_LENGTH = 300
EXPIRED_REASON = "승인 기한 지남"


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def _text(value: str, limit: int, label: str, code: str) -> str:
    text = value.strip()
    _rule(0 < len(text) <= limit, f"{label}을(를) 1~{limit:,}자로 적어 주세요.", code)
    return text


def clean_reason(reason: str) -> str:
    return _text(reason, REASON_MAX_LENGTH, "사유", "invalid_reason")


def _on_boundary(value: datetime) -> bool:
    local = value.astimezone(KST)
    return local.minute % SLOT_MINUTES == 0 and local.second == 0 and local.microsecond == 0


@dataclass(kw_only=True, eq=False)
class MentoringRequest(AggregateRoot):
    requester_id: uuid.UUID  # 신청한 수강 등록(students.id)
    mentor_id: uuid.UUID
    topic: str
    detail: str
    desired_times: list[datetime]  # 1~3순위 시작 시각
    duration: int  # 분
    team_id: uuid.UUID | None = None  # 없으면 1:1
    replaced_request_id: uuid.UUID | None = None
    status: MentoringRequestStatus = MentoringRequestStatus.PENDING
    rejected_at: datetime | None = None
    reject_reason: str | None = None
    canceled_at: datetime | None = None
    cancel_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.topic = _text(self.topic, TOPIC_MAX_LENGTH, "주제", "invalid_request_topic")
        self.detail = _text(self.detail, DETAIL_MAX_LENGTH, "내용", "invalid_request_detail")
        _rule(
            0 < self.duration <= MAX_DURATION_MINUTES and self.duration % SLOT_MINUTES == 0,
            f"신청 시간은 {MAX_DURATION_MINUTES}분 이하입니다.",
            "invalid_request_duration",
        )
        _rule(
            1 <= len(self.desired_times) <= MAX_DESIRED,
            f"희망 일시는 1~{MAX_DESIRED}개입니다.",
            "invalid_desired_times",
        )
        _rule(
            all(t.tzinfo is not None for t in self.desired_times),
            "희망 일시에 시간대가 필요합니다.",
            "invalid_desired_times",
        )
        self.desired_times = [t.astimezone(UTC) for t in self.desired_times]
        _rule(
            all(_on_boundary(t) for t in self.desired_times),
            "희망 일시는 정각 또는 30분에 시작합니다.",
            "invalid_desired_times",
        )
        ordered = sorted(self.slots())
        _rule(
            all(a[1] <= b[0] for a, b in pairwise(ordered)),
            "희망 일시끼리 겹치면 안 됩니다.",
            "desired_times_overlap",
        )

    def slots(self) -> list[tuple[datetime, datetime]]:
        length = timedelta(minutes=self.duration)
        return [(t, t + length) for t in self.desired_times]

    def ensure_duration_unit(self, allowed_duration: int) -> None:
        _rule(
            self.duration % allowed_duration == 0,
            f"신청 시간은 {allowed_duration}분 단위입니다.",
            "invalid_request_duration",
        )

    @property
    def is_team(self) -> bool:
        return self.team_id is not None

    def approvable_times(self, now: datetime) -> list[datetime]:
        """아직 시작하지 않은 희망 일시 (승인은 시작 전까지, A42)."""
        return [t for t in self.desired_times if t > now]

    def is_stale(self, now: datetime) -> bool:
        return self.status is MentoringRequestStatus.PENDING and not self.approvable_times(now)

    def approve(self, starts_at: datetime, *, now: datetime) -> tuple[datetime, datetime]:
        """희망 일시 하나를 골라 승인한다. (시작, 종료)를 돌려준다."""
        self._ensure_pending("승인")
        _rule(starts_at.tzinfo is not None, "일시에 시간대가 필요합니다.", "not_desired_time")
        chosen = starts_at.astimezone(UTC)
        _rule(chosen in self.desired_times, "희망 일시 중에서 골라 주세요.", "not_desired_time")
        _rule(chosen > now, "이미 시작 시각이 지난 희망 일시입니다.", "desired_time_passed")
        self.status = MentoringRequestStatus.APPROVED
        return chosen, chosen + timedelta(minutes=self.duration)

    def reject(self, reason: str, *, now: datetime) -> None:
        self._ensure_pending("반려")
        cleaned = clean_reason(reason)
        self.status = MentoringRequestStatus.REJECTED
        self.rejected_at = now
        self.reject_reason = cleaned

    def _ensure_pending(self, action: str) -> None:
        _rule(
            self.status is MentoringRequestStatus.PENDING,
            f"대기 중인 신청만 {action}할 수 있습니다.",
            "request_not_pending",
        )

    def cancel(self, reason: str, *, now: datetime) -> None:
        """대기 중이거나 승인된 신청을 취소한다. 마감·권한은 서비스가 본다."""
        _rule(
            self.status in (MentoringRequestStatus.PENDING, MentoringRequestStatus.APPROVED),
            "대기 중이거나 승인된 신청만 취소할 수 있습니다.",
            "request_not_cancelable",
        )
        cleaned = clean_reason(reason)  # 검증을 먼저 해 실패해도 상태가 바뀌지 않게 한다
        self.status = MentoringRequestStatus.CANCELED
        self.canceled_at = now
        self.cancel_reason = cleaned


def ensure_before_deadline(starts_at: datetime, *, min_lead_hours: int, now: datetime) -> None:
    """수강생·멘토의 승인 후 취소·변경은 시작 min_lead_hours 전까지 (M26)."""
    _rule(
        now <= starts_at - timedelta(hours=min_lead_hours),
        f"시작 {min_lead_hours}시간 전까지만 취소·변경할 수 있습니다. 운영진에게 문의해 주세요.",
        "cancel_deadline_passed",
    )

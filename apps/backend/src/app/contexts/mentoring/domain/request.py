"""멘토링 신청 (decisions M1·M3·M5·M9·A41·A42).

- 수강생 본인만 신청한다(대리 신청 없음). 팀 신청은 팀원 누구나, 취소·변경은 신청자만.
- 희망 일시 1~3개, 각각 30분 경계, 서로 겹치지 않는다. 신청 시간은 진행 단위의 배수, 최대 120분.
- 주제 100자, 상세 내용 필수 2,000자. 반려·취소 사유 필수 300자.
- 상태: PENDING → APPROVED / REJECTED / CANCELED (승인 후 취소는 P11-3).
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

    def cancel(self, reason: str, *, now: datetime) -> None:
        _rule(
            self.status is MentoringRequestStatus.PENDING,
            "대기 중인 신청만 취소할 수 있습니다.",
            "request_not_pending",
        )
        cleaned = clean_reason(reason)  # 검증을 먼저 해 실패해도 상태가 바뀌지 않게 한다
        self.status = MentoringRequestStatus.CANCELED
        self.canceled_at = now
        self.cancel_reason = cleaned

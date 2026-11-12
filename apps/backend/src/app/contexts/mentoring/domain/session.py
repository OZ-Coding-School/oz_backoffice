"""멘토링 세션 (decisions M3·A42·A43).

- 승인된 신청 하나에 세션 하나가 생긴다(SCHEDULED).
- 제목은 자동: "신청자(팀 이름 또는 수강생 이름) · 멘토 표시 이름 멘토링 N회차"(100자),
  N은 같은 신청자·같은 멘토의 취소되지 않은 세션 순서. 주제는 신청 주제.
- 멘토 일정 겹침은 DB EXCLUDE가, 신청자 일정 겹침은 서비스가 막는다.
- 진행·기록·Meet·녹화 필드는 P12·P13에서 채운다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.mentoring.domain.enums import MentoringSessionStatus, RecordingStatus
from app.shared.domain import AggregateRoot

TITLE_MAX_LENGTH = 100


def session_title(requester_label: str, mentor_label: str, number: int) -> str:
    suffix = f" 멘토링 {number}회차"
    head = f"{requester_label} · {mentor_label}"
    return head[: TITLE_MAX_LENGTH - len(suffix)] + suffix


@dataclass(kw_only=True, eq=False)
class MentoringSession(AggregateRoot):
    mentor_id: uuid.UUID
    request_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    title: str
    topic: str
    status: MentoringSessionStatus = MentoringSessionStatus.SCHEDULED
    body: str | None = None
    record_duration_minutes: int | None = None
    recorded_at: datetime | None = None
    google_space_name: str | None = None
    google_meet_url: str | None = None
    google_conference_record_name: str | None = None
    actual_started_at: datetime | None = None
    actual_ended_at: datetime | None = None
    recording_status: RecordingStatus = RecordingStatus.PENDING
    recording_started_at: datetime | None = None
    recording_ended_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

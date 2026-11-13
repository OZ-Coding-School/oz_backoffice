"""멘토링 세션 (decisions M3·A42·A43).

- 승인된 신청 하나에 세션 하나가 생긴다(SCHEDULED).
- 제목은 자동: "신청자(팀 이름 또는 수강생 이름) · 멘토 표시 이름 멘토링 N회차"(100자),
  N은 같은 신청자·같은 멘토의 취소되지 않은 세션 순서. 주제는 신청 주제.
- 멘토 일정 겹침은 DB EXCLUDE가, 신청자 일정 겹침은 서비스가 막는다.
- Meet 공간은 승인 후 만들고(링크 = `google_meet_url`), 취소되면 막고 링크를 지운다(A48).
- 진행·기록·녹화 필드는 P12-2·P13에서 채운다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.mentoring.domain.enums import MentoringSessionStatus, RecordingStatus
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

TITLE_MAX_LENGTH = 100


@dataclass(frozen=True, slots=True)
class SessionQuery:
    """세션 목록 조건 (시작 시각 최신순)."""

    status: MentoringSessionStatus | None = None
    starts_from: datetime | None = None  # 포함
    starts_before: datetime | None = None  # 미포함
    limit: int = 20
    offset: int = 0


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

    def cancel(self) -> None:
        """예정 세션만 취소한다(시작 시각이 지났어도 기록 전이면 가능, A44)."""
        if self.status is not MentoringSessionStatus.SCHEDULED:
            raise BusinessRuleViolation(
                "예정된 세션만 취소할 수 있습니다.", code="session_not_cancelable"
            )
        self.status = MentoringSessionStatus.CANCELED

    @property
    def needs_space(self) -> bool:
        """Meet 공간을 만들어야 하는 세션 (예정이고 아직 공간이 없음, A48)."""
        return self.status is MentoringSessionStatus.SCHEDULED and self.google_space_name is None

    @property
    def needs_space_closed(self) -> bool:
        """취소됐는데 아직 링크가 살아 있는 세션 (공간을 막아야 함)."""
        return self.status is MentoringSessionStatus.CANCELED and self.google_meet_url is not None

    def attach_space(self, name: str, meeting_uri: str) -> None:
        if self.google_space_name is not None:
            raise BusinessRuleViolation("이미 Meet 공간이 있습니다.", code="meet_space_exists")
        self.google_space_name = name
        self.google_meet_url = meeting_uri

    def space_closed(self) -> None:
        """공간을 막았다: 링크를 지운다(공간 이름은 기록으로 남긴다)."""
        self.google_meet_url = None

    def conference_started(self, record_name: str, at: datetime | None) -> bool:
        """Meet 회의 시작 이벤트 (A49): 처음 시작 시각, 첫 회의 기록 이름. 바뀌었으면 True."""
        return self._conference(record_name, started=at)

    def conference_ended(self, record_name: str, at: datetime | None) -> bool:
        """Meet 회의 종료 이벤트 (A49): 마지막 종료 시각. 바뀌었으면 True."""
        return self._conference(record_name, ended=at)

    def recording_generated(self) -> bool:
        if self.status is MentoringSessionStatus.CANCELED:
            return False
        if self.recording_status is RecordingStatus.FILE_GENERATED:
            return False
        self.recording_status = RecordingStatus.FILE_GENERATED
        return True

    def _conference(
        self,
        record_name: str,
        *,
        started: datetime | None = None,
        ended: datetime | None = None,
    ) -> bool:
        """취소된 세션은 무시. 진행 상태는 IN_PROGRESS까지만(완료·노쇼는 멘토 기록, M27).

        이벤트 순서가 뒤바뀌거나 중복돼도 결과가 같다(최솟값·최댓값만 남김).
        """
        if self.status is MentoringSessionStatus.CANCELED:
            return False
        before = (
            self.status,
            self.actual_started_at,
            self.actual_ended_at,
            self.google_conference_record_name,
        )
        if self.status is MentoringSessionStatus.SCHEDULED:
            self.status = MentoringSessionStatus.IN_PROGRESS
        if self.google_conference_record_name is None:
            self.google_conference_record_name = record_name
        if started is not None and (
            self.actual_started_at is None or started < self.actual_started_at
        ):
            self.actual_started_at = started
        if ended is not None and (self.actual_ended_at is None or ended > self.actual_ended_at):
            self.actual_ended_at = ended
        return before != (
            self.status,
            self.actual_started_at,
            self.actual_ended_at,
            self.google_conference_record_name,
        )

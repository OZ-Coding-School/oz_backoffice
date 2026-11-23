"""멘토링 세션 (decisions M3·A42·A43).

- 승인된 신청 하나에 세션 하나가 생긴다(SCHEDULED).
- 제목은 자동: "신청자(팀 이름 또는 수강생 이름) · 멘토 표시 이름 멘토링 N회차"(100자),
  N은 같은 신청자·같은 멘토의 취소되지 않은 세션 순서. 주제는 신청 주제.
- 멘토 일정 겹침은 DB EXCLUDE가, 신청자 일정 겹침은 서비스가 막는다.
- Meet 공간은 승인 후 만들고(링크 = `google_meet_url`), 취소되면 막고 링크를 지운다(A48).
- 기록(A53): 담당 멘토가 예정 시작 시각 이후 COMPLETED(실제 진행 시간 30분 단위·주제·요약 필수)
  또는 NO_SHOW(사유 선택)를 제출한다. 진행 시간·완료/노쇼는 처음 제출로 고정, 주제·요약은 제출 후
  7일까지 수정.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contexts.mentoring.domain.enums import MentoringSessionStatus, RecordingStatus
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

TITLE_MAX_LENGTH = 100
TOPIC_MAX_LENGTH = 100
SUMMARY_MAX_LENGTH = 5000
RECORD_UNIT_MINUTES = 30
RECORD_EDIT_DAYS = 7


@dataclass(frozen=True, slots=True)
class SessionQuery:
    """세션 목록 조건 (기본은 시작 시각 최신순, `ascending`이면 이른 순, A75)."""

    status: MentoringSessionStatus | None = None
    statuses: tuple[MentoringSessionStatus, ...] = ()  # 여러 개 (수강생·멘토 목록, A70)
    starts_from: datetime | None = None  # 포함
    starts_before: datetime | None = None  # 미포함
    ascending: bool = False  # 시작 시각 이른 순 (수강생·멘토 목록, A75)
    limit: int = 20
    offset: int = 0


def _rule(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def _text(value: str, limit: int, label: str, code: str) -> str:
    text = value.strip()
    _rule(0 < len(text) <= limit, f"{label}을(를) 1~{limit:,}자로 적어 주세요.", code)
    return text


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

    # ------------------------------------------------------------------ 기록 (A53)
    @property
    def is_recorded(self) -> bool:
        return self.recorded_at is not None

    def submit_completed(self, *, duration: int, topic: str, summary: str, now: datetime) -> None:
        _rule(
            duration > 0 and duration % RECORD_UNIT_MINUTES == 0,
            "진행 시간은 30분 단위로 적어 주세요.",
            "invalid_record_duration",
        )
        topic_text = _text(topic, TOPIC_MAX_LENGTH, "주제", "invalid_record_topic")
        summary_text = _text(summary, SUMMARY_MAX_LENGTH, "요약", "invalid_record_summary")
        self._ensure_recordable(now)
        self.status = MentoringSessionStatus.COMPLETED
        self.record_duration_minutes = duration
        self.topic = topic_text
        self.body = summary_text
        self.recorded_at = now

    def submit_no_show(self, *, reason: str | None, now: datetime) -> None:
        text = (reason or "").strip()
        _rule(len(text) <= SUMMARY_MAX_LENGTH, "사유가 너무 깁니다.", "invalid_record_summary")
        self._ensure_recordable(now)
        self.status = MentoringSessionStatus.NO_SHOW
        self.record_duration_minutes = None
        self.body = text or None
        self.recorded_at = now

    def edit_record(self, *, topic: str | None, summary: str | None, now: datetime) -> None:
        """주제·요약만, 제출 후 7일까지 (A53)."""
        recorded_at = self.recorded_at
        if recorded_at is None:
            raise BusinessRuleViolation("아직 제출한 기록이 없습니다.", code="record_not_submitted")
        _rule(
            now <= recorded_at + timedelta(days=RECORD_EDIT_DAYS),
            f"기록은 제출 후 {RECORD_EDIT_DAYS}일까지만 고칠 수 있습니다.",
            "record_edit_expired",
        )
        if topic is not None:
            _rule(
                self.status is MentoringSessionStatus.COMPLETED,
                "노쇼 기록에는 주제를 고칠 수 없습니다.",
                "invalid_record_topic",
            )
            self.topic = _text(topic, TOPIC_MAX_LENGTH, "주제", "invalid_record_topic")
        if summary is not None:
            if self.status is MentoringSessionStatus.COMPLETED:
                self.body = _text(summary, SUMMARY_MAX_LENGTH, "요약", "invalid_record_summary")
            else:
                text = summary.strip()
                _rule(
                    len(text) <= SUMMARY_MAX_LENGTH, "사유가 너무 깁니다.", "invalid_record_summary"
                )
                self.body = text or None

    def _ensure_recordable(self, now: datetime) -> None:
        _rule(
            self.status in (MentoringSessionStatus.SCHEDULED, MentoringSessionStatus.IN_PROGRESS),
            "기록을 제출할 수 없는 세션입니다.",
            "session_not_recordable",
        )
        _rule(
            now >= self.starts_at,
            "예정 시작 시각 이후에 제출할 수 있습니다.",
            "session_not_started",
        )

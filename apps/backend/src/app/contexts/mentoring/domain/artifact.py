"""Meet 녹화·전사·스마트 메모 파일 (decisions M19·M20·A53·A54).

원본은 Drive에 두고(공유 드라이브 `멘토링 녹화/과정/기수/멘토 실명/YYYY-MM`로 정리) 백엔드가
중계한다.
- 수집: Meet API가 알려 준 세션 파일만 PENDING으로 만든다(세션·Drive 파일 ID 유니크, 중복 수신에
  안전).
- 정리: 폴더로 옮기고 이름·형식·크기를 채우면 COMPLETED. 세션 종료 7일이 지나도 못 하면 FAILED.
- 열람: COMPLETED만. 영상은 그대로, 문서(전사·요약)는 PDF로 내보낸다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.mentoring.domain.enums import MentoringArtifactStatus, MentoringArtifactType
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

PDF_MIME = "application/pdf"


@dataclass(kw_only=True, eq=False)
class MentoringArtifact(AggregateRoot):
    session_id: uuid.UUID
    drive_file_id: str
    artifact_type: MentoringArtifactType
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    status: MentoringArtifactStatus = MentoringArtifactStatus.PENDING
    conference_record: str | None = None  # 같은 회의의 영상·전사본을 짝짓는다 (A69)
    started_at: datetime | None = None  # 녹화 시작 (영상만, 전사 문장 위치 계산, A69)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_document(self) -> bool:
        """Google 문서(전사·요약)는 PDF로 내보내 보여 준다."""
        return self.artifact_type is not MentoringArtifactType.VIDEO

    @property
    def is_viewable(self) -> bool:
        return self.status is MentoringArtifactStatus.COMPLETED

    @property
    def needs_archive(self) -> bool:
        return self.status is MentoringArtifactStatus.PENDING

    def archived(self, *, file_name: str, mime_type: str, file_size: int | None) -> None:
        if self.status is not MentoringArtifactStatus.PENDING:
            raise BusinessRuleViolation("정리할 파일이 아닙니다.", code="artifact_not_pending")
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_size = file_size
        self.status = MentoringArtifactStatus.COMPLETED

    def link_conference(self, record: str | None, started_at: datetime | None) -> bool:
        """비어 있는 회의 기록·녹화 시작을 채운다. 바뀌었으면 True (수집 전에 만든 파일 보완)."""
        changed = False
        if record and self.conference_record is None:
            self.conference_record = record
            changed = True
        if started_at and self.started_at is None:
            self.started_at = started_at
            changed = True
        return changed

    def failed(self) -> None:
        if self.status is MentoringArtifactStatus.PENDING:
            self.status = MentoringArtifactStatus.FAILED

    @property
    def served_mime_type(self) -> str:
        return PDF_MIME if self.is_document else (self.mime_type or "video/mp4")

"""Meet 녹화·전사·요약 파일 도메인 (A53·A54)."""

import pytest

from app.contexts.mentoring.domain.artifact import PDF_MIME, MentoringArtifact
from app.contexts.mentoring.domain.enums import MentoringArtifactStatus, MentoringArtifactType
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def test_archive_and_fail() -> None:
    video = MentoringArtifact(
        session_id=new_id(), drive_file_id="f1", artifact_type=MentoringArtifactType.VIDEO
    )
    assert (video.needs_archive, video.is_viewable, video.is_document) == (True, False, False)
    video.archived(file_name="녹화.mp4", mime_type="video/mp4", file_size=10)
    assert (video.status, video.is_viewable, video.served_mime_type) == (
        MentoringArtifactStatus.COMPLETED,
        True,
        "video/mp4",
    )
    with pytest.raises(BusinessRuleViolation):
        video.archived(file_name="x", mime_type="y", file_size=None)
    video.failed()  # 완료된 파일은 실패로 바꾸지 않는다
    assert video.status is MentoringArtifactStatus.COMPLETED

    transcript = MentoringArtifact(
        session_id=new_id(), drive_file_id="d1", artifact_type=MentoringArtifactType.TRANSCRIPT
    )
    assert (transcript.is_document, transcript.served_mime_type) == (True, PDF_MIME)
    transcript.failed()
    assert transcript.status is MentoringArtifactStatus.FAILED

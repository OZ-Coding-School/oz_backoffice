"""전사 화자 이름 (A69)."""

from datetime import UTC, datetime

import pytest

from app.contexts.mentoring.domain.artifact import MentoringArtifact
from app.contexts.mentoring.domain.enums import MentoringArtifactType
from app.contexts.mentoring.domain.transcript import UNKNOWN_SPEAKER, name_key, speaker_name
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def test_speaker_name_maps_known_names_ignoring_space_and_case() -> None:
    aliases = {name_key("김 멘토"): "멘토K", name_key("Ga Sugang"): "가수강"}
    assert speaker_name("김멘토", aliases) == "멘토K"
    assert speaker_name(" ga  sugang ", aliases) == "가수강"
    assert speaker_name("모르는 사람", aliases) == "모르는 사람"  # Meet 이름 그대로
    assert speaker_name("  ", aliases) == UNKNOWN_SPEAKER
    assert len(speaker_name("가" * 200, aliases)) == 100


def test_link_conference_fills_only_empty_values() -> None:
    artifact = MentoringArtifact(
        session_id=new_id(), drive_file_id="v1", artifact_type=MentoringArtifactType.VIDEO
    )
    at = datetime(2026, 11, 20, 5, tzinfo=UTC)
    assert artifact.link_conference("conferenceRecords/c1", at) is True
    assert artifact.link_conference("conferenceRecords/c2", None) is False  # 이미 있음
    assert (artifact.conference_record, artifact.started_at) == ("conferenceRecords/c1", at)

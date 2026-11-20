"""Meet 전사 항목 (decisions A68·A69, BE-2c).

전사본 파일(artifact)마다 문장을 순서대로 저장한다. 문장 시각 − 같은 회의 녹화 시작 = 영상 위치.
화자는 Meet 표시 이름이 멘토 실명·닉네임이나 그 세션 참여 수강생 이름과 같으면 서비스 이름
(멘토는 표시 이름, 수강생은 이름)으로 바꾸고, 같은 이름이 없으면 Meet 표시 이름을 쓴다(A69).
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.shared.domain import Entity

SPEAKER_MAX_LENGTH = 100
UNKNOWN_SPEAKER = "참가자"


@dataclass(kw_only=True, eq=False)
class TranscriptEntry(Entity):
    artifact_id: uuid.UUID
    sequence: int  # 0부터, 문장 순서
    speaker_name: str  # 화면에 보일 이름
    meet_name: str  # Meet 표시 이름 (원본)
    text: str
    started_at: datetime
    ended_at: datetime | None = None


def name_key(name: str) -> str:
    """대조용: 공백을 빼고 대소문자를 무시한다."""
    return "".join(name.split()).casefold()


def speaker_name(meet_name: str, aliases: Mapping[str, str]) -> str:
    """Meet 표시 이름 → 서비스 이름 (같은 이름이 없으면 Meet 이름, 비어 있으면 '참가자')."""
    cleaned = meet_name.strip()
    if not cleaned:
        return UNKNOWN_SPEAKER
    return aliases.get(name_key(cleaned), cleaned)[:SPEAKER_MAX_LENGTH]

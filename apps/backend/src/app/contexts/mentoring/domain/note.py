"""멘토 내부 메모 (decisions M22·A53): 세션당 하나, 담당 멘토만 쓰고 멘토·운영진만 본다.

수강생 응답에는 없다. 작성·수정은 감사 로그에 남긴다(서비스).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

NOTE_MAX_LENGTH = 5000


def clean_note(body: str) -> str:
    text = body.strip()
    if not 0 < len(text) <= NOTE_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"메모를 1~{NOTE_MAX_LENGTH:,}자로 적어 주세요.", code="invalid_session_note"
        )
    return text


@dataclass(kw_only=True, eq=False)
class MentoringSessionNote(AggregateRoot):
    session_id: uuid.UUID
    body: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.body = clean_note(self.body)

    def rewrite(self, body: str) -> None:
        self.body = clean_note(body)

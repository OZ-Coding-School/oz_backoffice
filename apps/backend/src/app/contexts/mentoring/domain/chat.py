"""멘토링 채팅 (decisions M23·A57, P15).

- 채팅방은 1:1(수강 등록-멘토) 또는 팀(팀-담당 멘토) 중 하나다. (수강 등록, 멘토)·(팀, 멘토)당 하나.
  처음 메시지(또는 안내 메시지)를 남길 때 만든다(서비스).
- 메시지는 텍스트만 1~2,000자, 수정은 없다. 보낸 사람은 기한 없이 지울 수 있고, 지우면 본문을
  비우고 지운 시각을 남긴다. 보낸 사람이 없는(시스템 안내) 메시지는 지울 수 없다.
- 읽음 위치는 참여자별 마지막으로 본 메시지 ID이고 앞으로만 옮긴다(uuid7이라 ID 순서 = 시간 순서).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation, PermissionDeniedError

MESSAGE_MAX_LENGTH = 2000
DELETED_TEXT = "삭제된 메시지입니다."


class ChatThreadKind(StrEnum):
    DIRECT = "DIRECT"
    TEAM = "TEAM"


def clean_message(body: str) -> str:
    text = body.strip()
    if not 0 < len(text) <= MESSAGE_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"메시지를 1~{MESSAGE_MAX_LENGTH:,}자로 적어 주세요.", code="invalid_chat_message"
        )
    return text


@dataclass(kw_only=True, eq=False)
class ChatThread(AggregateRoot):
    mentor_id: uuid.UUID
    student_id: uuid.UUID | None = None  # 1:1
    team_id: uuid.UUID | None = None  # 팀
    last_message_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if (self.student_id is None) == (self.team_id is None):
            raise BusinessRuleViolation(
                "채팅방은 1:1 또는 팀 중 하나입니다.", code="invalid_chat_thread"
            )

    @property
    def kind(self) -> ChatThreadKind:
        return ChatThreadKind.TEAM if self.team_id else ChatThreadKind.DIRECT

    def touch(self, at: datetime) -> None:
        """새 메시지 시각으로 목록 정렬 기준을 옮긴다 (뒤로 가지 않음)."""
        if self.last_message_at is None or at > self.last_message_at:
            self.last_message_at = at


@dataclass(kw_only=True, eq=False)
class ChatMessage(AggregateRoot):
    thread_id: uuid.UUID
    sender_id: uuid.UUID | None  # users.id, None이면 시스템 안내
    body: str | None
    created_at: datetime
    deleted_at: datetime | None = None

    @classmethod
    def write(
        cls, thread_id: uuid.UUID, sender_id: uuid.UUID | None, body: str, *, now: datetime
    ) -> "ChatMessage":
        return cls(
            thread_id=thread_id, sender_id=sender_id, body=clean_message(body), created_at=now
        )

    @property
    def is_system(self) -> bool:
        return self.sender_id is None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, user_id: uuid.UUID, *, now: datetime) -> bool:
        """보낸 사람만 지운다. 이미 지웠으면 그대로(False)."""
        if self.is_system:
            raise BusinessRuleViolation(
                "안내 메시지는 지울 수 없습니다.", code="system_message_not_deletable"
            )
        if self.sender_id != user_id:
            raise PermissionDeniedError(
                "보낸 사람만 메시지를 지울 수 있습니다.", code="not_message_sender"
            )
        if self.is_deleted:
            return False
        self.body = None
        self.deleted_at = now
        return True


@dataclass(kw_only=True, eq=False)
class ChatRead:
    """참여자별 읽음 위치 ((방, 사용자) 복합 키)."""

    thread_id: uuid.UUID
    user_id: uuid.UUID
    last_read_message_id: uuid.UUID | None = None
    last_read_at: datetime | None = None

    def advance(self, message_id: uuid.UUID, *, now: datetime) -> bool:
        """앞으로만 옮긴다. 옮겼으면 True."""
        if self.last_read_message_id is not None and message_id <= self.last_read_message_id:
            return False
        self.last_read_message_id = message_id
        self.last_read_at = now
        return True

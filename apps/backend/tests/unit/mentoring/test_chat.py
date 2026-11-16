"""멘토링 채팅 도메인 (A57)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.domain.chat import (
    MESSAGE_MAX_LENGTH,
    ChatMessage,
    ChatRead,
    ChatThread,
    ChatThreadKind,
)
from app.shared.errors import BusinessRuleViolation, PermissionDeniedError
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


def test_thread_is_direct_or_team() -> None:
    assert ChatThread(mentor_id=new_id(), student_id=new_id()).kind is ChatThreadKind.DIRECT
    assert ChatThread(mentor_id=new_id(), team_id=new_id()).kind is ChatThreadKind.TEAM
    for kwargs in ({}, {"student_id": new_id(), "team_id": new_id()}):
        with pytest.raises(BusinessRuleViolation) as error:
            ChatThread(mentor_id=new_id(), **kwargs)  # type: ignore[arg-type]
        assert error.value.code == "invalid_chat_thread"


def test_thread_touch_only_moves_forward() -> None:
    thread = ChatThread(mentor_id=new_id(), student_id=new_id())
    thread.touch(NOW)
    thread.touch(NOW - timedelta(minutes=1))
    assert thread.last_message_at == NOW
    thread.touch(NOW + timedelta(seconds=1))
    assert thread.last_message_at == NOW + timedelta(seconds=1)


def test_message_body_is_trimmed_and_limited() -> None:
    message = ChatMessage.write(new_id(), new_id(), "  안녕하세요 \n", now=NOW)
    assert message.body == "안녕하세요"
    assert ChatMessage.write(new_id(), None, "가" * MESSAGE_MAX_LENGTH, now=NOW).is_system
    for body in ("   ", "가" * (MESSAGE_MAX_LENGTH + 1)):
        with pytest.raises(BusinessRuleViolation) as error:
            ChatMessage.write(new_id(), new_id(), body, now=NOW)
        assert error.value.code == "invalid_chat_message"


def test_sender_deletes_own_message_once() -> None:
    sender = new_id()
    message = ChatMessage.write(new_id(), sender, "지울 메시지", now=NOW)
    with pytest.raises(PermissionDeniedError) as other:
        message.delete(new_id(), now=NOW)
    assert other.value.code == "not_message_sender"
    assert message.delete(sender, now=NOW + timedelta(days=30)) is True  # 기한 없음
    assert message.is_deleted
    assert message.body is None
    assert message.deleted_at == NOW + timedelta(days=30)
    assert message.delete(sender, now=NOW + timedelta(days=31)) is False
    assert message.deleted_at == NOW + timedelta(days=30)


def test_system_message_cannot_be_deleted() -> None:
    message = ChatMessage.write(new_id(), None, "멘토링 신청이 접수됐습니다.", now=NOW)
    with pytest.raises(BusinessRuleViolation) as error:
        message.delete(new_id(), now=NOW)
    assert error.value.code == "system_message_not_deletable"


def test_read_position_moves_forward_only() -> None:
    first, second = new_id(), new_id()  # uuid7: 나중에 만든 것이 크다
    read = ChatRead(thread_id=new_id(), user_id=new_id())
    assert read.advance(second, now=NOW) is True
    assert read.advance(first, now=NOW + timedelta(minutes=1)) is False
    assert read.advance(second, now=NOW + timedelta(minutes=1)) is False
    assert (read.last_read_message_id, read.last_read_at) == (second, NOW)

"""mentoring 채팅 인메모리 리포지토리."""

import dataclasses
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from app.contexts.mentoring.domain.chat import ChatEvent, ChatMessage, ChatRead, ChatThread


class InMemoryChatStore:
    """방·메시지·읽음을 함께 둔다 (안 읽음 수가 셋을 모두 본다)."""

    def __init__(self, cohort_of: dict[uuid.UUID, uuid.UUID] | None = None) -> None:
        self.threads: dict[uuid.UUID, ChatThread] = {}
        self.messages: dict[uuid.UUID, ChatMessage] = {}
        self.reads: dict[tuple[uuid.UUID, uuid.UUID], ChatRead] = {}
        # 운영진 목록용: 수강 등록·팀 → 기수
        self.cohort_of = cohort_of if cohort_of is not None else {}
        self.thread_repo = InMemoryChatThreadRepository(self)
        self.message_repo = InMemoryChatMessageRepository(self)
        self.read_repo = InMemoryChatReadRepository(self)


def _sort_key(thread: ChatThread) -> tuple[datetime, uuid.UUID]:
    return (
        thread.last_message_at or thread.created_at or datetime.min.replace(tzinfo=UTC),
        thread.id,
    )


class InMemoryChatThreadRepository:
    def __init__(self, store: InMemoryChatStore) -> None:
        self._s = store

    async def get(self, thread_id: uuid.UUID) -> ChatThread | None:
        found = self._s.threads.get(thread_id)
        return dataclasses.replace(found) if found else None

    async def find(
        self, *, mentor_id: uuid.UUID, student_id: uuid.UUID | None, team_id: uuid.UUID | None
    ) -> ChatThread | None:
        for t in self._s.threads.values():
            if t.mentor_id != mentor_id:
                continue
            if (team_id is not None and t.team_id == team_id) or (
                team_id is None and t.team_id is None and t.student_id == student_id
            ):
                return dataclasses.replace(t)
        return None

    async def ensure(self, thread: ChatThread) -> ChatThread:
        found = await self.find(
            mentor_id=thread.mentor_id, student_id=thread.student_id, team_id=thread.team_id
        )
        if found is not None:
            return found
        self._s.threads[thread.id] = dataclasses.replace(thread)
        return dataclasses.replace(thread)

    async def touch(self, thread_id: uuid.UUID, at: datetime) -> None:
        self._s.threads[thread_id].touch(at)

    async def list_for(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        mentor_id: uuid.UUID | None,
    ) -> list[ChatThread]:
        found = [
            t
            for t in self._s.threads.values()
            if t.student_id in student_ids or t.team_id in team_ids or t.mentor_id == mentor_id
        ]
        return [dataclasses.replace(t) for t in sorted(found, key=_sort_key, reverse=True)]

    async def list_by_cohort(
        self,
        cohort_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID | None,
        limit: int,
        offset: int,
        student_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[ChatThread], int]:
        found = [
            t
            for t in self._s.threads.values()
            if self._s.cohort_of.get(t.team_id or t.student_id) == cohort_id  # type: ignore[arg-type]
            and (mentor_id is None or t.mentor_id == mentor_id)
            and (student_id is None or t.student_id == student_id)
            and (team_id is None or t.team_id == team_id)
        ]
        ordered = sorted(found, key=_sort_key, reverse=True)
        return [dataclasses.replace(t) for t in ordered[offset : offset + limit]], len(found)

    async def unread_counts(
        self, user_id: uuid.UUID, thread_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        result: dict[uuid.UUID, int] = {}
        for m in self._s.messages.values():
            if m.thread_id not in thread_ids or m.is_deleted or m.sender_id == user_id:
                continue
            read = self._s.reads.get((m.thread_id, user_id))
            if read and read.last_read_message_id and m.id <= read.last_read_message_id:
                continue
            result[m.thread_id] = result.get(m.thread_id, 0) + 1
        return result

    async def last_messages(self, thread_ids: list[uuid.UUID]) -> dict[uuid.UUID, ChatMessage]:
        result: dict[uuid.UUID, ChatMessage] = {}
        for m in sorted(self._s.messages.values(), key=lambda m: m.id):
            if m.thread_id in thread_ids:
                result[m.thread_id] = dataclasses.replace(m)
        return result


class InMemoryChatMessageRepository:
    def __init__(self, store: InMemoryChatStore) -> None:
        self._s = store

    async def add(self, message: ChatMessage) -> None:
        self._s.messages[message.id] = dataclasses.replace(message)

    async def save(self, message: ChatMessage) -> None:
        self._s.messages[message.id] = dataclasses.replace(message)

    async def get(self, message_id: uuid.UUID) -> ChatMessage | None:
        found = self._s.messages.get(message_id)
        return dataclasses.replace(found) if found else None

    async def list_before(
        self, thread_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[ChatMessage]:
        found = sorted(
            (
                m
                for m in self._s.messages.values()
                if m.thread_id == thread_id and (before is None or m.id < before)
            ),
            key=lambda m: m.id,
            reverse=True,
        )
        return [dataclasses.replace(m) for m in found[:limit]]


class InMemoryChatReadRepository:
    def __init__(self, store: InMemoryChatStore) -> None:
        self._s = store

    async def get(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> ChatRead | None:
        found = self._s.reads.get((thread_id, user_id))
        return dataclasses.replace(found) if found else None

    async def save(self, read: ChatRead) -> None:
        current = self._s.reads.get((read.thread_id, read.user_id))
        if (
            current is None
            or current.last_read_message_id is None
            or (
                read.last_read_message_id
                and current.last_read_message_id < read.last_read_message_id
            )
        ):
            self._s.reads[(read.thread_id, read.user_id)] = dataclasses.replace(read)


class RecordingChatEvents:
    """보낸 실시간 알림을 남긴다. `fail`이면 Redis 오류처럼 실패한다."""

    def __init__(self) -> None:
        self.sent: list[tuple[set[uuid.UUID], ChatEvent]] = []
        self.fail = False

    async def publish(self, user_ids: Iterable[uuid.UUID], event: ChatEvent) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.sent.append((set(user_ids), event))

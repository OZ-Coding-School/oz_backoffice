"""멘토링 채팅 리포지토리 구현 (decisions M23·A57).

읽음 위치(`mentoring_chat_reads`)는 복합 PK라 모델 없이 SQL로 다룬다.
안 읽음 수·마지막 메시지는 방 여러 개를 한 번의 쿼리로 구한다.
"""

import uuid
from datetime import datetime
from typing import Any

from tortoise import connections
from tortoise.expressions import F, Q
from tortoise.functions import Coalesce

from app.contexts.mentoring.domain.chat import ChatMessage, ChatRead, ChatThread
from app.contexts.mentoring.infrastructure.models import (
    MentoringChatMessageModel,
    MentoringChatThreadModel,
)


def _db() -> Any:
    """현재 트랜잭션(UoW) 안이면 그 연결."""
    return connections.get("default")


def _thread(row: MentoringChatThreadModel) -> ChatThread:
    return ChatThread(
        id=row.id,
        mentor_id=row.mentor_id,  # type: ignore[attr-defined]  # FK 컬럼 속성
        student_id=row.student_id,  # type: ignore[attr-defined]
        team_id=row.team_id,  # type: ignore[attr-defined]
        last_message_at=row.last_message_at,
        created_at=row.created_at,
    )


def _message(row: MentoringChatMessageModel) -> ChatMessage:
    return ChatMessage(
        id=row.id,
        thread_id=row.thread_id,  # type: ignore[attr-defined]
        sender_id=row.sender_id,  # type: ignore[attr-defined]
        body=row.body,
        created_at=row.created_at,
        deleted_at=row.deleted_at,
    )


def _ordered(query: Any) -> Any:
    # 마지막 메시지 시각(없으면 만든 시각) 최신순
    return query.annotate(sort_at=Coalesce("last_message_at", F("created_at"))).order_by(
        "-sort_at", "-id"
    )


class TortoiseChatThreadRepository:
    async def get(self, thread_id: uuid.UUID) -> ChatThread | None:
        row = await MentoringChatThreadModel.get_or_none(id=thread_id)
        return _thread(row) if row else None

    async def find(
        self, *, mentor_id: uuid.UUID, student_id: uuid.UUID | None, team_id: uuid.UUID | None
    ) -> ChatThread | None:
        query = MentoringChatThreadModel.filter(mentor_id=mentor_id)
        query = (
            query.filter(team_id=team_id)
            if team_id is not None
            else query.filter(student_id=student_id, team_id__isnull=True)
        )
        row = await query.first()
        return _thread(row) if row else None

    async def ensure(self, thread: ChatThread) -> ChatThread:
        await _db().execute_query(
            'INSERT INTO "mentoring_chat_threads" ("id", "student_id", "team_id", "mentor_id") '
            "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
            [thread.id, thread.student_id, thread.team_id, thread.mentor_id],
        )
        found = await self.find(
            mentor_id=thread.mentor_id, student_id=thread.student_id, team_id=thread.team_id
        )
        if found is None:  # 방금 만들었거나 이미 있으므로 생기지 않는다
            raise RuntimeError("채팅방을 만들지 못했습니다.")
        return found

    async def touch(self, thread_id: uuid.UUID, at: datetime) -> None:
        await MentoringChatThreadModel.filter(
            Q(id=thread_id) & (Q(last_message_at__isnull=True) | Q(last_message_at__lt=at))
        ).update(last_message_at=at)

    async def list_for(
        self,
        *,
        student_ids: list[uuid.UUID],
        team_ids: list[uuid.UUID],
        mentor_id: uuid.UUID | None,
    ) -> list[ChatThread]:
        conditions = []
        if student_ids:
            conditions.append(Q(student_id__in=student_ids))
        if team_ids:
            conditions.append(Q(team_id__in=team_ids))
        if mentor_id is not None:
            conditions.append(Q(mentor_id=mentor_id))
        if not conditions:
            return []
        condition = Q(*conditions, join_type=Q.OR)
        rows = await _ordered(MentoringChatThreadModel.filter(condition))
        return [_thread(row) for row in rows]

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
        # 1:1은 수강 등록의 기수, 팀은 팀의 기수 (조인한 쿼리에 정렬식을 붙이면 Tortoise가
        # 컬럼 이름을 한정하지 않아 SQL로 id만 고른다)
        _, rows = await _db().execute_query(
            'SELECT t."id", count(*) OVER () AS "total" FROM "mentoring_chat_threads" t '
            'LEFT JOIN "students" s ON s."id" = t."student_id" '
            'LEFT JOIN "mentoring_teams" m ON m."id" = t."team_id" '
            'WHERE (s."cohort_id" = $1 OR m."cohort_id" = $1) '
            'AND ($2::uuid IS NULL OR t."mentor_id" = $2) '
            # 방 주인 필터 (A59): 1:1 방은 student_id, 팀 방은 team_id만 있다
            'AND ($5::uuid IS NULL OR t."student_id" = $5) '
            'AND ($6::uuid IS NULL OR t."team_id" = $6) '
            'ORDER BY COALESCE(t."last_message_at", t."created_at") DESC, t."id" DESC '
            "LIMIT $3 OFFSET $4",
            [cohort_id, mentor_id, limit, offset, student_id, team_id],
        )
        if not rows:
            total = 0
            if offset:
                total = await self._count_by_cohort(cohort_id, mentor_id, student_id, team_id)
            return [], total
        ids = [row["id"] for row in rows]
        found = {row.id: _thread(row) for row in await MentoringChatThreadModel.filter(id__in=ids)}
        return [found[i] for i in ids], int(rows[0]["total"])

    @staticmethod
    async def _count_by_cohort(
        cohort_id: uuid.UUID,
        mentor_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
    ) -> int:
        _, rows = await _db().execute_query(
            'SELECT count(*) AS "total" FROM "mentoring_chat_threads" t '
            'LEFT JOIN "students" s ON s."id" = t."student_id" '
            'LEFT JOIN "mentoring_teams" m ON m."id" = t."team_id" '
            'WHERE (s."cohort_id" = $1 OR m."cohort_id" = $1) '
            'AND ($2::uuid IS NULL OR t."mentor_id" = $2) '
            'AND ($3::uuid IS NULL OR t."student_id" = $3) '
            'AND ($4::uuid IS NULL OR t."team_id" = $4)',
            [cohort_id, mentor_id, student_id, team_id],
        )
        return int(rows[0]["total"])

    async def unread_counts(
        self, user_id: uuid.UUID, thread_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        if not thread_ids:
            return {}
        _, rows = await _db().execute_query(
            'SELECT m."thread_id", count(*) AS "unread" FROM "mentoring_chat_messages" m '
            'LEFT JOIN "mentoring_chat_reads" r '
            'ON r."thread_id" = m."thread_id" AND r."user_id" = $1 '
            'WHERE m."thread_id" = ANY($2::uuid[]) AND m."deleted_at" IS NULL '
            'AND m."sender_id" IS DISTINCT FROM $1 '
            'AND (r."last_read_message_id" IS NULL OR m."id" > r."last_read_message_id") '
            'GROUP BY m."thread_id"',
            [user_id, thread_ids],
        )
        return {row["thread_id"]: int(row["unread"]) for row in rows}

    async def last_messages(self, thread_ids: list[uuid.UUID]) -> dict[uuid.UUID, ChatMessage]:
        if not thread_ids:
            return {}
        _, rows = await _db().execute_query(
            'SELECT DISTINCT ON ("thread_id") "id" FROM "mentoring_chat_messages" '
            'WHERE "thread_id" = ANY($1::uuid[]) ORDER BY "thread_id", "id" DESC',
            [thread_ids],
        )
        found = await MentoringChatMessageModel.filter(id__in=[row["id"] for row in rows])
        return {message.thread_id: message for message in map(_message, found)}


class TortoiseChatMessageRepository:
    async def add(self, message: ChatMessage) -> None:
        await MentoringChatMessageModel.create(
            id=message.id,
            thread_id=message.thread_id,
            sender_id=message.sender_id,
            body=message.body,
            created_at=message.created_at,
            deleted_at=message.deleted_at,
        )

    async def save(self, message: ChatMessage) -> None:
        await MentoringChatMessageModel.filter(id=message.id).update(
            body=message.body, deleted_at=message.deleted_at
        )

    async def get(self, message_id: uuid.UUID) -> ChatMessage | None:
        row = await MentoringChatMessageModel.get_or_none(id=message_id)
        return _message(row) if row else None

    async def list_before(
        self, thread_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
    ) -> list[ChatMessage]:
        query = MentoringChatMessageModel.filter(thread_id=thread_id)
        if before is not None:
            query = query.filter(id__lt=before)
        rows = await query.order_by("-id").limit(limit)
        return [_message(row) for row in rows]


class TortoiseChatReadRepository:
    async def get(self, thread_id: uuid.UUID, user_id: uuid.UUID) -> ChatRead | None:
        _, rows = await _db().execute_query(
            'SELECT "last_read_message_id", "last_read_at" FROM "mentoring_chat_reads" '
            'WHERE "thread_id" = $1 AND "user_id" = $2',
            [thread_id, user_id],
        )
        if not rows:
            return None
        return ChatRead(
            thread_id=thread_id,
            user_id=user_id,
            last_read_message_id=rows[0]["last_read_message_id"],
            last_read_at=rows[0]["last_read_at"],
        )

    async def save(self, read: ChatRead) -> None:
        # 동시에 저장해도 뒤로 가지 않게 SQL에서도 앞으로만 옮긴다
        await _db().execute_query(
            'INSERT INTO "mentoring_chat_reads" '
            '("thread_id", "user_id", "last_read_message_id", "last_read_at") '
            "VALUES ($1, $2, $3, $4) "
            'ON CONFLICT ("thread_id", "user_id") DO UPDATE SET '
            '"last_read_message_id" = EXCLUDED."last_read_message_id", '
            '"last_read_at" = EXCLUDED."last_read_at" '
            'WHERE "mentoring_chat_reads"."last_read_message_id" IS NULL '
            'OR "mentoring_chat_reads"."last_read_message_id" < EXCLUDED."last_read_message_id"',
            [read.thread_id, read.user_id, read.last_read_message_id, read.last_read_at],
        )

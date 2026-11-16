"""멘토링 채팅 저장·조회와 DB 제약 (A57)."""

from datetime import UTC, datetime, timedelta

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.domain.entities import Cohort
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.mentoring.domain.chat import ChatMessage, ChatRead, ChatThread
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.chat_repositories import (
    TortoiseChatMessageRepository,
    TortoiseChatReadRepository,
    TortoiseChatThreadRepository,
)
from app.contexts.mentoring.infrastructure.repositories import TortoiseMentoringTeamRepository
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor, create_user

pytestmark = pytest.mark.integration

threads = TortoiseChatThreadRepository()
messages = TortoiseChatMessageRepository()
reads = TortoiseChatReadRepository()
NOW = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)


async def _setup() -> tuple[ChatThread, ChatThread, Cohort, Mentor]:
    cohort = await create_cohort()
    mentor = await create_mentor()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    team = MentoringTeam(
        cohort_id=cohort.id, team_number=1, mentor_id=mentor.id, member_ids=[student.id]
    )
    await TortoiseMentoringTeamRepository().add(team)
    direct = await threads.ensure(ChatThread(mentor_id=mentor.id, student_id=student.id))
    team_thread = await threads.ensure(ChatThread(mentor_id=mentor.id, team_id=team.id))
    return direct, team_thread, cohort, mentor


async def test_thread_ensure_is_idempotent_and_constraints() -> None:
    direct, team_thread, cohort, mentor = await _setup()
    again = await threads.ensure(
        ChatThread(mentor_id=direct.mentor_id, student_id=direct.student_id)
    )
    assert again.id == direct.id
    assert (
        await threads.find(mentor_id=direct.mentor_id, student_id=direct.student_id, team_id=None)
    ) == direct
    assert (
        await threads.find(
            mentor_id=team_thread.mentor_id, student_id=None, team_id=team_thread.team_id
        )
    ) == team_thread

    db = connections.get("default")
    with pytest.raises(IntegrityError):  # 1:1/팀 중 하나
        await db.execute_query(
            "UPDATE mentoring_chat_threads SET team_id = $1 WHERE id = $2",
            [str(team_thread.team_id), str(direct.id)],
        )
    with pytest.raises(IntegrityError):  # (수강 등록, 멘토) 부분 유니크
        await db.execute_query(
            "INSERT INTO mentoring_chat_threads (id, student_id, mentor_id) VALUES ($1, $2, $3)",
            [str(new_id()), str(direct.student_id), str(mentor.id)],
        )

    page, total = await threads.list_by_cohort(cohort.id, mentor_id=None, limit=10, offset=0)
    assert total == 2
    assert {t.id for t in page} == {direct.id, team_thread.id}
    second, second_total = await threads.list_by_cohort(
        cohort.id, mentor_id=mentor.id, limit=1, offset=1
    )
    assert second_total == 2
    assert len(second) == 1
    assert await threads.list_by_cohort(cohort.id, mentor_id=None, limit=5, offset=5) == ([], 2)
    assert await threads.list_by_cohort(cohort.id, mentor_id=new_id(), limit=5, offset=0) == (
        [],
        0,
    )
    other, other_total = await threads.list_by_cohort(
        (await create_cohort()).id, mentor_id=None, limit=10, offset=0
    )
    assert (other, other_total) == ([], 0)
    # 방 주인 필터 (A59)
    by_student, _ = await threads.list_by_cohort(
        cohort.id, mentor_id=None, limit=10, offset=0, student_id=direct.student_id
    )
    by_team, _ = await threads.list_by_cohort(
        cohort.id, mentor_id=None, limit=10, offset=0, team_id=team_thread.team_id
    )
    assert ([t.id for t in by_student], [t.id for t in by_team]) == ([direct.id], [team_thread.id])
    assert await threads.list_by_cohort(
        cohort.id, mentor_id=None, limit=10, offset=5, team_id=team_thread.team_id
    ) == ([], 1)  # 빈 페이지의 전체 수도 필터를 따른다


async def test_messages_cursor_delete_and_last_message() -> None:
    direct, team_thread, _, _ = await _setup()
    sender = await create_user()
    sent = []
    for i in range(5):
        message = ChatMessage.write(
            direct.id, sender.id, f"메시지 {i}", now=NOW + timedelta(seconds=i)
        )
        await messages.add(message)
        await threads.touch(direct.id, message.created_at)
        sent.append(message)
    await threads.touch(direct.id, NOW - timedelta(days=1))  # 뒤로 가지 않음

    newest = await messages.list_before(direct.id, before=None, limit=2)
    assert [m.body for m in newest] == ["메시지 4", "메시지 3"]
    older = await messages.list_before(direct.id, before=newest[-1].id, limit=10)
    assert [m.body for m in older] == ["메시지 2", "메시지 1", "메시지 0"]

    target = sent[4]
    target.delete(sender.id, now=NOW + timedelta(minutes=1))
    await messages.save(target)
    loaded = await messages.get(target.id)
    assert loaded is not None
    assert loaded.body is None
    assert loaded.deleted_at == NOW + timedelta(minutes=1)

    last = await threads.last_messages([direct.id, team_thread.id])
    assert list(last) == [direct.id]
    assert last[direct.id].id == target.id
    refreshed = await threads.get(direct.id)
    assert refreshed is not None
    assert refreshed.last_message_at == NOW + timedelta(seconds=4)
    db = connections.get("default")
    await db.execute_query(
        "UPDATE mentoring_chat_threads SET created_at = $1 WHERE id = $2",
        [NOW + timedelta(seconds=2), str(team_thread.id)],
    )
    ordered = await threads.list_for(student_ids=[], team_ids=[], mentor_id=direct.mentor_id)
    assert [t.id for t in ordered] == [direct.id, team_thread.id]  # 메시지 없으면 만든 시각
    await db.execute_query(
        "UPDATE mentoring_chat_threads SET created_at = $1 WHERE id = $2",
        [NOW + timedelta(seconds=5), str(team_thread.id)],
    )
    ordered = await threads.list_for(student_ids=[], team_ids=[], mentor_id=direct.mentor_id)
    assert [t.id for t in ordered] == [team_thread.id, direct.id]

    with pytest.raises(IntegrityError):  # 지운 메시지는 본문이 없다
        await db.execute_query(
            "UPDATE mentoring_chat_messages SET body = 'x' WHERE id = $1", [str(target.id)]
        )
    system = ChatMessage.write(direct.id, None, "안내", now=NOW)
    await messages.add(system)
    with pytest.raises(IntegrityError):  # 안내 메시지는 지우지 않는다
        await db.execute_query(
            "UPDATE mentoring_chat_messages SET body = NULL, deleted_at = now() WHERE id = $1",
            [str(system.id)],
        )
    with pytest.raises(IntegrityError):  # 2,000자 초과
        await db.execute_query(
            "UPDATE mentoring_chat_messages SET body = repeat('가', 2001) WHERE id = $1",
            [str(sent[0].id)],
        )


async def test_unread_counts_follow_read_position() -> None:
    direct, team_thread, _, _ = await _setup()
    me, other = await create_user(), await create_user()
    mine = ChatMessage.write(direct.id, me.id, "내 메시지", now=NOW)
    await messages.add(mine)
    theirs = [ChatMessage.write(direct.id, other.id, f"상대 {i}", now=NOW) for i in range(3)]
    for m in theirs:
        await messages.add(m)
    await messages.add(ChatMessage.write(direct.id, None, "안내", now=NOW))
    await messages.add(ChatMessage.write(team_thread.id, other.id, "팀", now=NOW))
    theirs[2].delete(other.id, now=NOW)
    await messages.save(theirs[2])

    # 내가 보낸 것·지운 것 제외, 안내 포함
    assert await threads.unread_counts(me.id, [direct.id, team_thread.id]) == {
        direct.id: 3,
        team_thread.id: 1,
    }
    assert await reads.get(direct.id, me.id) is None
    read = ChatRead(thread_id=direct.id, user_id=me.id)
    read.advance(theirs[1].id, now=NOW)
    await reads.save(read)
    assert (await threads.unread_counts(me.id, [direct.id]))[direct.id] == 1  # 안내만 남음

    # 이미 더 앞을 읽었으면 뒤로 가지 않는다 (SQL에서도)
    stale = ChatRead(thread_id=direct.id, user_id=me.id)
    stale.advance(theirs[0].id, now=NOW + timedelta(minutes=1))
    await reads.save(stale)
    loaded = await reads.get(direct.id, me.id)
    assert loaded is not None
    assert (loaded.last_read_message_id, loaded.last_read_at) == (theirs[1].id, NOW)

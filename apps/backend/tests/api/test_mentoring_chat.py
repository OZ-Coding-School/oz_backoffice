"""멘토링 채팅 API (실제 DB, A57·A74: 자격은 신청 이력)."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.mentoring.domain.chat import ChatEvent, ChatEventKind
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.infrastructure.repositories import TortoiseMentoringRequestRepository
from app.contexts.mentoring.presentation.chat_router import (
    ChatPresenter,
    StreamRenderer,
    get_chat_service,
)
from app.core.clock import SystemClock
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.access import ASSISTANT, give_role
from tests.factories.educator import create_mentor, create_mentor_contract, create_user
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

CHAT = "/api/v1/mentoring/chat"
MY_THREADS = "/api/v1/me/mentoring/chat/threads"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


async def _approved(**overrides: Any) -> User:
    user = await create_user(**overrides)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _setup(client: AsyncClient, settings: Settings) -> dict[str, Any]:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    api = f"/api/v1/admin/cohorts/{cohort.id}"
    mentor_user = await _approved(name="김멘토")
    mentor = await create_mentor(
        mentor_user, nickname="멘토K", display_name_preference=DisplayNamePreference.NICKNAME
    )
    assigned = await client.post(
        f"{api}/mentor-assignments",
        json={
            "mentor_id": str(mentor.id),
            "start_date": "2026-11-01",
            "contract_id": str(
                (
                    await create_mentor_contract(
                        mentor.id, bootcamp_id=cohort.bootcamp_id, cohort_id=cohort.id
                    )
                ).id
            ),
        },
        headers=admin,
    )
    assert assigned.status_code == 201, assigned.text
    await client.put(
        f"{api}/mentoring-settings", json={"allow_team_mentoring": True}, headers=admin
    )
    repo = TortoiseStudentRepository()
    users = [await _approved(name=name) for name in ("가수강", "나수강", "다수강")]
    students = [make_student(cohort_id=cohort.id, name=u.name, user_id=u.id) for u in users]
    for s in students:
        await repo.add(s)
    team = await client.post(
        f"{api}/mentoring-teams",
        json={
            "mentor_id": str(mentor.id),
            "student_ids": [str(students[0].id), str(students[1].id)],
        },
        headers=admin,
    )
    assert team.status_code == 201, team.text
    # 채팅 자격은 신청 이력 (A74): 가수강·다수강 1:1, 팀 신청
    requests = TortoiseMentoringRequestRepository()
    for student, team_id in (
        (students[0], None),
        (students[2], None),
        (students[0], uuid.UUID(team.json()["id"])),
    ):
        await requests.add(
            MentoringRequest(
                requester_id=student.id,
                mentor_id=mentor.id,
                team_id=team_id,
                topic="질문",
                detail="내용",
                desired_times=[datetime(2026, 12, 1, 5, tzinfo=UTC)],
                duration=60,
            )
        )
    return {
        "admin": admin,
        "cohort": cohort,
        "admin_path": f"{api}/mentoring/chat/threads",
        "mentor": mentor,
        "mentor_h": bearer(settings, mentor_user),
        "students": students,
        "student_h": [bearer(settings, u) for u in users],
        "team_id": team.json()["id"],
    }


async def test_direct_chat_flow(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    me, mentor_h = ctx["student_h"][0], ctx["mentor_h"]
    started = await client.post(
        f"{CHAT}/messages",
        json={
            "cohort_id": str(ctx["cohort"].id),
            "mentor_id": str(ctx["mentor"].id),
            "body": " 질문 있습니다 ",
        },
        headers=me,
    )
    assert started.status_code == 201, started.text
    first = started.json()
    assert (first["body"], first["sender_kind"], first["sender_name"]) == (
        "질문 있습니다",
        "STUDENT",
        "가수강",
    )
    thread_url = f"{CHAT}/threads/{first['thread_id']}"

    reply = await client.post(f"{thread_url}/messages", json={"body": "답변"}, headers=mentor_h)
    assert reply.status_code == 201, reply.text
    assert (reply.json()["sender_kind"], reply.json()["sender_name"]) == ("MENTOR", "멘토K")

    mine = (await client.get(MY_THREADS, headers=me)).json()
    assert mine["total"] == 1
    (thread,) = mine["items"]
    assert (thread["kind"], thread["student_name"], thread["mentor_display_name"]) == (
        "DIRECT",
        "가수강",
        "멘토K",
    )
    assert "mentor_name" not in thread
    assert thread["unread_count"] == 1
    assert thread["last_message"]["id"] == reply.json()["id"]

    page = (await client.get(f"{thread_url}/messages?limit=1", headers=me)).json()
    assert [m["body"] for m in page["items"]] == ["답변"]
    rest = (
        await client.get(f"{thread_url}/messages?before={page['next_before']}", headers=me)
    ).json()
    assert ([m["body"] for m in rest["items"]], rest["next_before"]) == (["질문 있습니다"], None)

    read = await client.put(
        f"{thread_url}/read", json={"message_id": reply.json()["id"]}, headers=me
    )
    assert read.json()["unread_count"] == 0

    not_mine = await client.delete(f"{thread_url}/messages/{reply.json()['id']}", headers=me)
    assert (not_mine.status_code, not_mine.json()["error"]["code"]) == (403, "not_message_sender")
    deleted = await client.delete(f"{thread_url}/messages/{first['id']}", headers=me)
    assert (deleted.json()["is_deleted"], deleted.json()["body"]) == (True, None)

    empty = await client.post(f"{thread_url}/messages", json={"body": "  "}, headers=me)
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "invalid_chat_message")
    outsider = ctx["student_h"][1]  # 같은 기수의 다른 수강생 (이 방의 참여자가 아니다)
    for response in (
        await client.get(thread_url, headers=outsider),
        await client.get(f"{thread_url}/messages", headers=outsider),
        await client.post(f"{thread_url}/messages", json={"body": "끼어들기"}, headers=outsider),
    ):
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "chat_thread_not_found",
        )
    assert (await client.get(MY_THREADS)).status_code == 401


async def test_team_chat_and_staff_view(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    started = await client.post(
        f"{CHAT}/messages",
        json={"team_id": ctx["team_id"], "body": "팀 질문"},
        headers=ctx["student_h"][0],
    )
    assert started.status_code == 201, started.text
    teammate = (await client.get(MY_THREADS, headers=ctx["student_h"][1])).json()
    assert [(t["kind"], t["team_label"], t["unread_count"]) for t in teammate["items"]] == [
        ("TEAM", "1팀", 1)
    ]
    assert (await client.get(MY_THREADS, headers=ctx["student_h"][2])).json()["total"] == 0
    outsider = await client.post(
        f"{CHAT}/messages",
        json={"team_id": ctx["team_id"], "body": "끼어들기"},
        headers=ctx["student_h"][2],
    )
    assert outsider.status_code == 404
    by_mentor = await client.post(
        f"{CHAT}/messages",
        json={"student_id": str(ctx["students"][2].id), "body": "안녕하세요"},
        headers=ctx["mentor_h"],
    )
    assert by_mentor.status_code == 201, by_mentor.text

    admin_path, admin = ctx["admin_path"], ctx["admin"]
    listed = (await client.get(admin_path, headers=admin)).json()
    assert listed["total"] == 2
    by_team = (
        await client.get(admin_path, params={"team_id": ctx["team_id"]}, headers=admin)
    ).json()
    by_student = (
        await client.get(
            admin_path, params={"student_id": str(ctx["students"][2].id)}, headers=admin
        )
    ).json()
    assert [t["kind"] for t in by_team["items"]] == ["TEAM"]  # 방 주인 필터 (A59)
    assert [t["kind"] for t in by_student["items"]] == ["DIRECT"]
    assert {(t["kind"], t["mentor_name"]) for t in listed["items"]} == {
        ("TEAM", "김멘토"),
        ("DIRECT", "김멘토"),
    }
    thread_id = started.json()["thread_id"]
    one = await client.get(f"{admin_path}/{thread_id}", headers=admin)
    assert one.json()["unread_count"] == 0
    messages = (await client.get(f"{admin_path}/{thread_id}/messages", headers=admin)).json()
    assert [m["body"] for m in messages["items"]] == ["팀 질문"]
    assistant_user = await create_applicant()
    assistant_user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(assistant_user)
    await give_role(assistant_user.id, ASSISTANT, cohort_id=ctx["cohort"].id)
    assistant = bearer(settings, assistant_user)
    assert (await client.get(admin_path, headers=assistant)).status_code == 200
    other_cohort = await create_cohort()
    other_path = f"/api/v1/admin/cohorts/{other_cohort.id}/mentoring/chat/threads"
    assert (await client.get(other_path, headers=assistant)).status_code == 403
    assert (await client.get(f"{other_path}/{thread_id}", headers=admin)).status_code == 404
    assert (await client.get(admin_path, headers=ctx["student_h"][0])).status_code == 403
    assert (await client.get(admin_path)).status_code == 401


async def test_stream_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/me/mentoring/chat/stream")).status_code == 401


async def test_stream_renders_events_for_each_receiver(
    client: AsyncClient, settings: Settings, app: FastAPI, fake_redis: FakeAsyncRedis
) -> None:
    """SSE가 받은 알림을 받는 사람 기준으로 다시 읽어 프레임을 만든다 (ASGI 테스트 클라이언트는
    끝나지 않는 응답을 읽지 못해 렌더러를 직접 부른다)."""
    ctx = await _setup(client, settings)
    sent = await client.post(
        f"{CHAT}/messages",
        json={"team_id": ctx["team_id"], "body": "팀 질문"},
        headers=ctx["student_h"][0],
    )
    message = sent.json()
    thread_id, message_id = uuid.UUID(message["thread_id"]), uuid.UUID(message["id"])
    request = cast("Any", SimpleNamespace(app=app))
    service = get_chat_service(request, SystemClock())
    presenter = ChatPresenter(request)

    def renderer(student_index: int) -> StreamRenderer:
        return StreamRenderer(service, presenter, ctx["students"][student_index].user_id)

    new = ChatEvent(ChatEventKind.MESSAGE, thread_id, message_id)
    frame = await renderer(1)(new)
    assert frame is not None
    assert frame.startswith("event: message\ndata: ")
    assert '"body":"팀 질문"' in frame
    assert '"sender_name":"가수강"' in frame
    assert await renderer(2)(new) is None  # 팀원이 아니면 건너뛴다

    read = await renderer(1)(ChatEvent(ChatEventKind.READ, thread_id))
    assert read is not None
    assert read.startswith("event: read\ndata: ")
    assert '"unread_count":1' in read

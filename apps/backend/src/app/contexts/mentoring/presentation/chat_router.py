"""멘토링 채팅 API (decisions M23·A57, P15-1).

참여자 (수강생·멘토, 자격이 없으면 404):
  GET    /me/mentoring/chat/threads                          참여 중인 방 (마지막 메시지 최신순)
  GET    /me/mentoring/chat/stream                           실시간 수신 (SSE, A58)
  POST   /mentoring/chat/messages                            상대를 골라 보내기 (방이 없으면 만듦)
  GET    /mentoring/chat/threads/{id}                         방
  GET    /mentoring/chat/threads/{id}/messages?before=&limit= 메시지 (최신부터, 커서)
  POST   /mentoring/chat/threads/{id}/messages                보내기
  DELETE /mentoring/chat/threads/{id}/messages/{message_id}   본인 메시지 삭제
  PUT    /mentoring/chat/threads/{id}/read                    읽음 (본 마지막 메시지, 앞으로만)
운영진 (mentoring.request.read, 기수 범위, 열람만):
  GET    /admin/cohorts/{cohort_id}/mentoring/chat/threads?mentor_id=
  GET    /admin/cohorts/{cohort_id}/mentoring/chat/threads/{id}
  GET    /admin/cohorts/{cohort_id}/mentoring/chat/threads/{id}/messages?before=&limit=
수강생·멘토 응답에는 멘토 표시 이름만, 운영진 응답에만 멘토 실명을 넣는다(A28).
"""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.chat_service import (
    MESSAGE_PAGE_DEFAULT,
    ChatService,
    ChatTarget,
    StudentLookup,
    ThreadView,
)
from app.contexts.mentoring.domain.chat import (
    ChatEvent,
    ChatEventKind,
    ChatMessage,
    ChatThread,
    ChatThreadKind,
)
from app.contexts.mentoring.infrastructure.chat_events import RedisChatEvents
from app.contexts.mentoring.infrastructure.chat_repositories import (
    TortoiseChatMessageRepository,
    TortoiseChatReadRepository,
    TortoiseChatThreadRepository,
)
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseCohortMentorRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.pagination import Page
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError

router = APIRouter(prefix="/mentoring/chat", tags=["mentoring-chat"])
me_router = APIRouter(prefix="/me/mentoring/chat", tags=["mentoring-chat"])
admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring/chat/threads", tags=["admin-mentoring-chat"]
)

ChatReader = Annotated[
    User, Depends(require_permission("mentoring.request.read", cohort_param="cohort_id"))
]
Before = Annotated[uuid.UUID | None, Query(description="이 메시지보다 앞선 것 (다음 페이지 커서)")]
Limit = Annotated[int, Query(ge=1, le=100)]


def get_chat_service(
    request: Request,
    clock: Annotated[Clock, Depends(get_clock)],
    redis: Annotated["Redis", Depends(get_redis)],
) -> ChatService:
    state = request.app.state
    return ChatService(
        threads=TortoiseChatThreadRepository(),
        messages=TortoiseChatMessageRepository(),
        reads=TortoiseChatReadRepository(),
        teams=TortoiseMentoringTeamRepository(),
        assignments=TortoiseCohortMentorRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        events=RedisChatEvents(redis),
        uow=UnitOfWork(),
        clock=clock,
    )


ServiceDep = Annotated[ChatService, Depends(get_chat_service)]


# ---------------------------------------------------------------- 스키마
class SenderKind(StrEnum):
    SYSTEM = "SYSTEM"
    MENTOR = "MENTOR"
    STUDENT = "STUDENT"


class MessageResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    sender_kind: SenderKind
    sender_id: uuid.UUID | None = Field(description="보낸 회원(users.id), 안내 메시지는 null")
    sender_name: str | None = Field(description="멘토는 표시 이름, 수강생은 이름")
    body: str | None = Field(description="삭제된 메시지는 null")
    is_deleted: bool
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageResponse] = Field(description="최신부터")
    next_before: uuid.UUID | None = Field(description="다음 페이지 커서 (없으면 끝)")


class ThreadResponse(BaseModel):
    id: uuid.UUID
    kind: ChatThreadKind
    cohort_id: uuid.UUID
    student_id: uuid.UUID | None = Field(description="1:1 방의 수강 등록")
    student_name: str | None
    team_id: uuid.UUID | None
    team_label: str | None
    mentor_id: uuid.UUID
    mentor_display_name: str
    last_message_at: datetime | None
    last_message: MessageResponse | None
    unread_count: int = Field(description="안 읽은 메시지 수 (운영진 응답은 0)")


class AdminThreadResponse(ThreadResponse):
    mentor_name: str = Field(description="멘토 실명 (운영진 응답에만)")


class SendBody(BaseModel):
    body: str = Field(description="1~2,000자 (앞뒤 공백 제외)")


class StartBody(SendBody):
    """상대 하나: 팀(`team_id`), 수강생→멘토(`cohort_id`·`mentor_id`), 멘토→수강생(`student_id`)."""

    team_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None


class ReadBody(BaseModel):
    message_id: uuid.UUID = Field(description="본 마지막 메시지")


# ---------------------------------------------------------------- 이름 붙이기
class ChatPresenter:
    def __init__(self, request: Request) -> None:
        state = request.app.state
        self._students = cast("StudentLookup", state.student_queries)
        self._mentors = cast("MentorDirectory", state.mentor_queries)
        self._users = cast("UserQueries", state.user_queries)
        self._threads = TortoiseChatThreadRepository()
        self._teams = TortoiseMentoringTeamRepository()

    async def messages(
        self, items: list[ChatMessage], threads: dict[uuid.UUID, ChatThread] | None = None
    ) -> list[MessageResponse]:
        """메시지 목록은 방 하나라 방을 하나씩 읽는다(방 목록은 이미 읽은 방을 넘긴다)."""
        if threads is None:
            threads = {
                t.id: t
                for t in [await self._threads.get(i) for i in {m.thread_id for m in items}]
                if t is not None
            }
        mentors = await self._mentors.get_many(list({t.mentor_id for t in threads.values()}))
        senders = await self._users.get_many([m.sender_id for m in items if m.sender_id])
        mentor_users = await self._users.get_many([m.user_id for m in mentors.values()])
        result = []
        for m in items:
            thread = threads.get(m.thread_id)
            mentor = mentors.get(thread.mentor_id) if thread else None
            if m.sender_id is None:
                kind, name = SenderKind.SYSTEM, None
            elif mentor is not None and mentor.user_id == m.sender_id:
                real = mentor_users[mentor.user_id].name if mentor.user_id in mentor_users else ""
                kind, name = SenderKind.MENTOR, mentor.display_name(real)
            else:
                sender = senders.get(m.sender_id)
                kind, name = SenderKind.STUDENT, sender.name if sender else None
            result.append(
                MessageResponse(
                    id=m.id,
                    thread_id=m.thread_id,
                    sender_kind=kind,
                    sender_id=m.sender_id,
                    sender_name=name,
                    body=m.body,
                    is_deleted=m.is_deleted,
                    created_at=m.created_at,
                )
            )
        return result

    async def admin(self, views: list[ThreadView]) -> list[AdminThreadResponse]:
        threads = [v.thread for v in views]
        students = await self._students.get_many([t.student_id for t in threads if t.student_id])
        teams = {
            t.id: t
            for t in await self._teams.list_by_ids([t.team_id for t in threads if t.team_id])
        }
        mentors = await self._mentors.get_many(list({t.mentor_id for t in threads}))
        users = await self._users.get_many([m.user_id for m in mentors.values()])
        lasts = await self.messages(
            [v.last_message for v in views if v.last_message], {t.id: t for t in threads}
        )
        last_by_thread = {m.thread_id: m for m in lasts}
        result = []
        for v in views:
            t = v.thread
            mentor = mentors.get(t.mentor_id)
            user = users.get(mentor.user_id) if mentor else None
            real = user.name if user else ""
            student = students.get(t.student_id) if t.student_id else None
            team = teams.get(t.team_id) if t.team_id else None
            result.append(
                AdminThreadResponse(
                    id=t.id,
                    kind=t.kind,
                    cohort_id=v.cohort_id,
                    student_id=t.student_id,
                    student_name=student.name if student else None,
                    team_id=t.team_id,
                    team_label=team.label if team else None,
                    mentor_id=t.mentor_id,
                    mentor_display_name=mentor.display_name(real) if mentor else "",
                    mentor_name=real,
                    last_message_at=t.last_message_at,
                    last_message=last_by_thread.get(t.id),
                    unread_count=v.unread_count,
                )
            )
        return result

    async def public(self, views: list[ThreadView]) -> list[ThreadResponse]:
        return [
            ThreadResponse(**r.model_dump(exclude={"mentor_name"})) for r in await self.admin(views)
        ]


PresenterDep = Annotated[ChatPresenter, Depends(ChatPresenter)]


async def _page(presenter: ChatPresenter, items: list[ChatMessage], limit: int) -> MessagePage:
    return MessagePage(
        items=await presenter.messages(items),
        next_before=items[-1].id if len(items) == limit else None,
    )


# ---------------------------------------------------------------- 참여자
@me_router.get("/threads", response_model=Page[ThreadResponse])
async def my_threads(
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ThreadResponse]:
    views, total = await service.list_threads(user.id, limit=limit, offset=offset)
    return Page(items=await presenter.public(views), total=total, limit=limit, offset=offset)


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def start(
    body: StartBody, user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> MessageResponse:
    target = ChatTarget(
        team_id=body.team_id,
        cohort_id=body.cohort_id,
        mentor_id=body.mentor_id,
        student_id=body.student_id,
    )
    message = await service.start(user.id, target, body.body)
    return (await presenter.messages([message]))[0]


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: uuid.UUID, user: ApprovedUser, service: ServiceDep, presenter: PresenterDep
) -> ThreadResponse:
    return (await presenter.public([await service.get_thread(user.id, thread_id)]))[0]


@router.get("/threads/{thread_id}/messages", response_model=MessagePage)
async def list_messages(
    thread_id: uuid.UUID,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
    before: Before = None,
    limit: Limit = MESSAGE_PAGE_DEFAULT,
) -> MessagePage:
    items = await service.list_messages(user.id, thread_id, before=before, limit=limit)
    return await _page(presenter, items, limit)


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send(
    thread_id: uuid.UUID,
    body: SendBody,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> MessageResponse:
    message = await service.send(user.id, thread_id, body.body)
    return (await presenter.messages([message]))[0]


@router.delete("/threads/{thread_id}/messages/{message_id}", response_model=MessageResponse)
async def delete_message(
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> MessageResponse:
    message = await service.delete_message(user.id, thread_id, message_id)
    return (await presenter.messages([message]))[0]


@router.put("/threads/{thread_id}/read", response_model=ThreadResponse)
async def mark_read(
    thread_id: uuid.UUID,
    body: ReadBody,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
) -> ThreadResponse:
    view = await service.mark_read(user.id, thread_id, body.message_id)
    return (await presenter.public([view]))[0]


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[AdminThreadResponse])
async def cohort_threads(
    cohort_id: uuid.UUID,
    _: ChatReader,
    service: ServiceDep,
    presenter: PresenterDep,
    mentor_id: uuid.UUID | None = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminThreadResponse]:
    views, total = await service.list_by_cohort(
        cohort_id, mentor_id=mentor_id, limit=limit, offset=offset
    )
    return Page(items=await presenter.admin(views), total=total, limit=limit, offset=offset)


@admin_router.get("/{thread_id}", response_model=AdminThreadResponse)
async def cohort_thread(
    cohort_id: uuid.UUID,
    thread_id: uuid.UUID,
    _: ChatReader,
    service: ServiceDep,
    presenter: PresenterDep,
) -> AdminThreadResponse:
    return (await presenter.admin([await service.get_for_cohort(cohort_id, thread_id)]))[0]


@admin_router.get("/{thread_id}/messages", response_model=MessagePage)
async def cohort_thread_messages(
    cohort_id: uuid.UUID,
    thread_id: uuid.UUID,
    _: ChatReader,
    service: ServiceDep,
    presenter: PresenterDep,
    before: Before = None,
    limit: Limit = MESSAGE_PAGE_DEFAULT,
) -> MessagePage:
    items = await service.messages_for_cohort(cohort_id, thread_id, before=before, limit=limit)
    return await _page(presenter, items, limit)


# ---------------------------------------------------------------- 실시간 수신 (SSE)
HEARTBEAT_SECONDS = 15.0  # 프록시가 유휴 연결을 끊지 않게 보내는 주석 줄 간격
RETRY_MILLISECONDS = 3000  # 끊기면 브라우저가 다시 붙기까지 기다리는 시간
STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",  # nginx가 버퍼링하지 않게 (운영 참고사항)
}


def sse_frame(event: str, data: BaseModel) -> str:
    return f"event: {event}\ndata: {data.model_dump_json()}\n\n"


class StreamRenderer:
    """알림을 받은 사람 기준으로 다시 읽어 SSE 프레임을 만든다. 볼 수 없게 됐으면 None."""

    def __init__(self, service: ChatService, presenter: ChatPresenter, user_id: uuid.UUID) -> None:
        self._service = service
        self._presenter = presenter
        self._user_id = user_id

    async def __call__(self, event: ChatEvent) -> str | None:
        try:
            if event.kind is ChatEventKind.READ:
                view = await self._service.get_thread(self._user_id, event.thread_id)
                return sse_frame(event.kind.value, (await self._presenter.public([view]))[0])
            if event.message_id is None:
                return None
            message = await self._service.get_message(
                self._user_id, event.thread_id, event.message_id
            )
        except NotFoundError:
            return None
        return sse_frame(event.kind.value, (await self._presenter.messages([message]))[0])


async def chat_stream(
    events: AsyncGenerator[ChatEvent | None],
    render: Callable[[ChatEvent], Awaitable[str | None]],
    disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    """`ready` 뒤 알림을 프레임으로, 조용하면 주석 줄(ping)을 보낸다. 연결이 끊기면 끝낸다."""
    try:
        yield f"retry: {RETRY_MILLISECONDS}\nevent: ready\ndata: {{}}\n\n"
        async for event in events:
            if await disconnected():
                break
            if event is None:
                yield ": ping\n\n"
                continue
            frame = await render(event)
            if frame is not None:
                yield frame
    finally:
        await events.aclose()


@me_router.get(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream(
    request: Request,
    user: ApprovedUser,
    service: ServiceDep,
    presenter: PresenterDep,
    redis: Annotated["Redis", Depends(get_redis)],
) -> StreamingResponse:
    """내가 참여한 모든 방의 `message`·`message_deleted`(MessageResponse), `read`(ThreadResponse).

    Authorization 헤더로 연결한다(fetch 기반 SSE). 끊긴 사이의 알림은 다시 보내지 않으므로
    다시 연결하면 방 목록·열린 방 메시지를 다시 조회한다 (A58).
    """
    events = RedisChatEvents(redis).subscribe(user.id, idle_seconds=HEARTBEAT_SECONDS)
    return StreamingResponse(
        chat_stream(events, StreamRenderer(service, presenter, user.id), request.is_disconnected),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )

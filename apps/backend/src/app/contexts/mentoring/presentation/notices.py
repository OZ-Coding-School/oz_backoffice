"""채팅 서비스·멘토링 안내 조립 (채팅 라우터와 신청·승인·기록·자동 정리 라우터가 같이 쓴다)."""

from typing import cast

from fastapi import Request

from app.contexts.mentoring.application.assignment_service import MentorDirectory
from app.contexts.mentoring.application.chat_notices import MentoringNotices
from app.contexts.mentoring.application.chat_service import (
    ChatEventPublisher,
    ChatService,
    StudentLookup,
)
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
from app.core.uow import UnitOfWork


def build_chat_service(request: Request, clock: Clock) -> ChatService:
    state = request.app.state
    return ChatService(
        threads=TortoiseChatThreadRepository(),
        messages=TortoiseChatMessageRepository(),
        reads=TortoiseChatReadRepository(),
        teams=TortoiseMentoringTeamRepository(),
        assignments=TortoiseCohortMentorRepository(),
        students=cast("StudentLookup", state.student_queries),
        mentors=cast("MentorDirectory", state.mentor_queries),
        events=cast("ChatEventPublisher", state.chat_events),
        uow=UnitOfWork(),
        clock=clock,
    )


def build_notices(request: Request, clock: Clock) -> MentoringNotices:
    return MentoringNotices(build_chat_service(request, clock))

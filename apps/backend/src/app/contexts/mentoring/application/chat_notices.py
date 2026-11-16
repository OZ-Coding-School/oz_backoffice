"""멘토링 이벤트 채팅 안내 (decisions A57·A58, P15-2).

신청·승인·반려, 취소·변경(자동 취소 포함), 기록 제출 때 그 신청의 방(1:1은 신청자-멘토, 팀은
팀-멘토)에 시스템 안내를 남긴다. 일시(KST)·주제·사유를 담고, 기록은 완료/노쇼와 진행 시간만.
호출한 서비스의 트랜잭션 안에서 부르며, 안내가 실패해도 원래 처리는 그대로다(ChatService).
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.contexts.mentoring.domain.chat import ChatMessage
from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.shared.time import KST

WEEKDAYS = "월화수목금토일"


class NoticePoster(Protocol):
    """mentoring `ChatService`."""

    async def post_notice(
        self,
        *,
        mentor_id: uuid.UUID,
        student_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        body: str,
    ) -> ChatMessage | None: ...


def _day(at: datetime) -> str:
    local = at.astimezone(KST)
    return f"{local.month}/{local.day}({WEEKDAYS[local.weekday()]}) {local:%H:%M}"


def _span(start: datetime, end: datetime) -> str:
    return f"{_day(start)}~{end.astimezone(KST):%H:%M}"


def _join(tag: str, *parts: str | None) -> str:
    """`[태그] 항목 · 항목` (빈 항목은 뺀다)."""
    return f"{tag} " + " · ".join(p for p in parts if p)


class MentoringNotices:
    def __init__(self, chat: NoticePoster) -> None:
        self._chat = chat

    async def requested(self, request: MentoringRequest) -> None:
        await self._post(request, _join("[멘토링 신청]", *self._detail(request)))

    async def changed(self, request: MentoringRequest) -> None:
        await self._post(request, _join("[멘토링 변경]", *self._detail(request)))

    async def approved(self, request: MentoringRequest, session: MentoringSession) -> None:
        await self._post(
            request,
            _join(
                "[멘토링 승인]",
                _span(session.starts_at, session.ends_at),
                f"주제: {request.topic}",
            ),
        )

    async def rejected(self, request: MentoringRequest) -> None:
        await self._post(
            request,
            _join("[멘토링 반려]", f"주제: {request.topic}", f"사유: {request.reject_reason}"),
        )

    async def canceled(
        self, request: MentoringRequest, session: MentoringSession | None = None
    ) -> None:
        await self._post(
            request,
            _join(
                "[멘토링 취소]",
                _span(session.starts_at, session.ends_at) if session else None,
                f"주제: {request.topic}",
                f"사유: {request.cancel_reason}" if request.cancel_reason else None,
            ),
        )

    async def recorded(self, request: MentoringRequest, session: MentoringSession) -> None:
        if session.status is MentoringSessionStatus.NO_SHOW:
            text = _join("[멘토링 노쇼]", _span(session.starts_at, session.ends_at))
        else:
            text = _join(
                "[멘토링 완료]",
                _span(session.starts_at, session.ends_at),
                f"진행 {session.record_duration_minutes}분",
            )
        await self._post(request, text)

    @staticmethod
    def _detail(request: MentoringRequest) -> list[str]:
        return [
            f"주제: {request.topic}",
            f"{request.duration}분",
            "희망 일시: " + ", ".join(_day(start) for start, _ in request.slots()),
        ]

    async def _post(self, request: MentoringRequest, body: str) -> None:
        await self._chat.post_notice(
            mentor_id=request.mentor_id,
            student_id=None if request.team_id else request.requester_id,
            team_id=request.team_id,
            body=body,
        )

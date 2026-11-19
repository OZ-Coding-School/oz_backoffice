"""멘토링 이벤트 채팅 안내 문구 (A58)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.application.chat_notices import MentoringNotices
from app.contexts.mentoring.domain.chat import ChatMessage
from app.contexts.mentoring.domain.enums import MentoringCancelActor
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

START = datetime(2026, 11, 20, 5, 0, tzinfo=UTC)  # 11/20(금) 14:00 KST


class Poster:
    def __init__(self) -> None:
        self.posts: list[tuple[uuid.UUID | None, uuid.UUID | None, str]] = []

    async def post_notice(
        self,
        *,
        mentor_id: uuid.UUID,
        student_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        body: str,
    ) -> ChatMessage | None:
        self.posts.append((student_id, team_id, body))
        return None


def _request(**overrides: object) -> MentoringRequest:
    values: dict[str, object] = {
        "requester_id": new_id(),
        "mentor_id": new_id(),
        "topic": "이력서",
        "detail": "봐 주세요",
        "desired_times": [START, START + timedelta(days=1)],
        "duration": 60,
    }
    values.update(overrides)
    return MentoringRequest(**values)  # type: ignore[arg-type]


async def test_notice_texts() -> None:
    poster = Poster()
    notices = MentoringNotices(poster)
    request = _request()
    session = MentoringSession(
        mentor_id=request.mentor_id,
        request_id=request.id,
        starts_at=START,
        ends_at=START + timedelta(hours=1),
        title="t",
        topic="이력서",
    )
    await notices.requested(request)
    await notices.approved(request, session)
    request.cancel("개인 사정", now=START - timedelta(days=1), by=MentoringCancelActor.REQUESTER)
    await notices.canceled(request, session)
    assert [body for _, _, body in poster.posts] == [
        "[멘토링 신청] 주제: 이력서 · 60분 · 희망 일시: 11/20(금) 14:00, 11/21(토) 14:00",
        "[멘토링 승인] 11/20(금) 14:00~15:00 · 주제: 이력서",
        "[멘토링 취소] 11/20(금) 14:00~15:00 · 주제: 이력서 · 사유: 개인 사정",
    ]
    assert {(s, t) for s, t, _ in poster.posts} == {(request.requester_id, None)}

    team_request = _request(team_id=new_id())
    await notices.requested(team_request)
    assert poster.posts[-1][:2] == (None, team_request.team_id)  # 팀은 팀 방

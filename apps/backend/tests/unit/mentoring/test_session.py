"""멘토링 세션 도메인 (A42·A43)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.domain.enums import MentoringSessionStatus
from app.contexts.mentoring.domain.session import (
    TITLE_MAX_LENGTH,
    MentoringSession,
    session_title,
)
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def test_session_title() -> None:
    assert session_title("가수강", "김멘토", 3) == "가수강 · 김멘토 멘토링 3회차"
    long = session_title("팀" * 80, "멘" * 80, 12)
    assert len(long) == TITLE_MAX_LENGTH
    assert long.endswith(" 멘토링 12회차")


def test_cancel_only_scheduled() -> None:
    start = datetime(2026, 11, 20, 5, tzinfo=UTC)
    session = MentoringSession(
        mentor_id=new_id(),
        request_id=new_id(),
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        title="제목",
        topic="주제",
    )
    session.cancel()
    assert session.status is MentoringSessionStatus.CANCELED
    for status in (MentoringSessionStatus.IN_PROGRESS, MentoringSessionStatus.COMPLETED):
        session.status = status
        with pytest.raises(BusinessRuleViolation) as error:
            session.cancel()
        assert error.value.code == "session_not_cancelable"

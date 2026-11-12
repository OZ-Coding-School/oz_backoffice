"""멘토링 세션 도메인 (A42·A43)."""

import pytest

from app.contexts.mentoring.domain.session import TITLE_MAX_LENGTH, session_title

pytestmark = pytest.mark.unit


def test_session_title() -> None:
    assert session_title("가수강", "김멘토", 3) == "가수강 · 김멘토 멘토링 3회차"
    long = session_title("팀" * 80, "멘" * 80, 12)
    assert len(long) == TITLE_MAX_LENGTH
    assert long.endswith(" 멘토링 12회차")

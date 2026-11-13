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


def _scheduled() -> MentoringSession:
    start = datetime(2026, 11, 20, 5, tzinfo=UTC)
    return MentoringSession(
        mentor_id=new_id(),
        request_id=new_id(),
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        title="제목",
        topic="신청 주제",
    )


def test_submit_completed_rules() -> None:
    session = _scheduled()
    start = session.starts_at
    with pytest.raises(BusinessRuleViolation) as early:  # 예정 시작 전
        session.submit_completed(
            duration=60, topic="주제", summary="요약", now=start - timedelta(minutes=1)
        )
    assert early.value.code == "session_not_started"
    for duration, code in ((0, "invalid_record_duration"), (45, "invalid_record_duration")):
        with pytest.raises(BusinessRuleViolation) as bad:
            session.submit_completed(duration=duration, topic="주제", summary="요약", now=start)
        assert bad.value.code == code
    with pytest.raises(BusinessRuleViolation) as no_summary:
        session.submit_completed(duration=60, topic="주제", summary=" ", now=start)
    assert no_summary.value.code == "invalid_record_summary"

    session.submit_completed(
        duration=90, topic=" 실제 주제 ", summary="요약", now=start
    )  # 신청보다 길어도 됨
    assert (
        session.status,
        session.record_duration_minutes,
        session.topic,
        session.recorded_at,
    ) == (
        MentoringSessionStatus.COMPLETED,
        90,
        "실제 주제",
        start,
    )
    with pytest.raises(BusinessRuleViolation) as again:  # 진행 시간·완료/노쇼는 처음 제출로 고정
        session.submit_no_show(reason=None, now=start)
    assert again.value.code == "session_not_recordable"


def test_edit_record_within_7_days() -> None:
    session = _scheduled()
    with pytest.raises(BusinessRuleViolation) as none:
        session.edit_record(topic="t", summary=None, now=session.starts_at)
    assert none.value.code == "record_not_submitted"
    submitted = session.starts_at + timedelta(hours=1)
    session.submit_completed(duration=60, topic="주제", summary="요약", now=submitted)
    session.edit_record(
        topic="새 주제", summary="새 요약", now=submitted + timedelta(days=7)
    )  # 경계 허용
    assert (session.topic, session.body) == ("새 주제", "새 요약")
    with pytest.raises(BusinessRuleViolation) as late:
        session.edit_record(
            topic=None, summary="늦음", now=submitted + timedelta(days=7, seconds=1)
        )
    assert late.value.code == "record_edit_expired"


def test_no_show_reason_optional() -> None:
    session = _scheduled()
    session.submit_no_show(reason="  ", now=session.starts_at)
    assert (session.status, session.body, session.record_duration_minutes) == (
        MentoringSessionStatus.NO_SHOW,
        None,
        None,
    )
    session.edit_record(topic=None, summary="수강생 미접속", now=session.starts_at)
    assert session.body == "수강생 미접속"
    with pytest.raises(BusinessRuleViolation):  # 노쇼에는 주제가 없다
        session.edit_record(topic="주제", summary=None, now=session.starts_at)
    canceled = _scheduled()
    canceled.cancel()
    with pytest.raises(BusinessRuleViolation):
        canceled.submit_no_show(reason=None, now=canceled.starts_at)


def test_session_note() -> None:
    from app.contexts.mentoring.domain.note import MentoringSessionNote

    note = MentoringSessionNote(session_id=new_id(), body=" 다음엔 테스트 코드 ")
    assert note.body == "다음엔 테스트 코드"
    with pytest.raises(BusinessRuleViolation):
        note.rewrite("")
    with pytest.raises(BusinessRuleViolation):
        MentoringSessionNote(session_id=new_id(), body="가" * 5001)

"""멘토링 신청 도메인 (A42)."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.mentoring.domain.balance import BalanceAccount
from app.contexts.mentoring.domain.enums import (
    MentoringBalanceTransactionType,
    MentoringRequestStatus,
)
from app.contexts.mentoring.domain.request import MentoringRequest, ensure_before_deadline
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id
from app.shared.time import KST

pytestmark = pytest.mark.unit

T = datetime(2026, 11, 20, 14, tzinfo=KST)


def _request(**overrides: Any) -> MentoringRequest:
    values: dict[str, Any] = {
        "requester_id": new_id(),
        "mentor_id": new_id(),
        "topic": " 포트폴리오 리뷰 ",
        "detail": "프로젝트 구조를 봐 주세요.",
        "desired_times": [T],
        "duration": 60,
    }
    values.update(overrides)
    return MentoringRequest(**values)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"topic": " "}, "invalid_request_topic"),
        ({"topic": "가" * 101}, "invalid_request_topic"),
        ({"detail": ""}, "invalid_request_detail"),
        ({"detail": "가" * 2001}, "invalid_request_detail"),
        ({"duration": 0}, "invalid_request_duration"),
        ({"duration": 150}, "invalid_request_duration"),
        ({"duration": 45}, "invalid_request_duration"),
        ({"desired_times": []}, "invalid_desired_times"),
        (
            {
                "desired_times": [
                    T,
                    T + timedelta(hours=2),
                    T + timedelta(hours=4),
                    T + timedelta(hours=6),
                ]
            },
            "invalid_desired_times",
        ),
        ({"desired_times": [T.replace(minute=10)]}, "invalid_desired_times"),
        ({"desired_times": [datetime(2026, 11, 20, 14)]}, "invalid_desired_times"),
        ({"desired_times": [T, T + timedelta(minutes=30)]}, "desired_times_overlap"),
    ],
)
def test_request_rules(overrides: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as error:
        _request(**overrides)
    assert error.value.code == code


def test_request_normalizes_and_boundaries() -> None:
    request = _request(desired_times=[T, T + timedelta(hours=1)], duration=60)  # 맞닿음은 허용
    assert request.topic == "포트폴리오 리뷰"
    assert request.desired_times[0].tzinfo is UTC
    assert request.slots()[0] == (T, T + timedelta(hours=1))
    _request(duration=120, topic="가" * 100, detail="가" * 2000)
    request.ensure_duration_unit(30)
    with pytest.raises(BusinessRuleViolation):
        _request(duration=90).ensure_duration_unit(60)


def test_cancel_and_stale() -> None:
    request = _request(desired_times=[T, T + timedelta(days=1)])
    assert request.approvable_times(T) == [T + timedelta(days=1)]  # 시작한 일시는 제외
    assert not request.is_stale(T)
    assert request.is_stale(T + timedelta(days=1))
    with pytest.raises(BusinessRuleViolation):
        request.cancel(" ", now=T)
    request.cancel("일정 변경", now=T)
    assert (request.status, request.cancel_reason) == (MentoringRequestStatus.CANCELED, "일정 변경")
    assert not request.is_stale(T + timedelta(days=2))
    with pytest.raises(BusinessRuleViolation) as twice:
        request.cancel("다시", now=T)
    assert twice.value.code == "request_not_cancelable"


def test_hold_and_release() -> None:
    account = BalanceAccount(
        student_id=new_id(), valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
    )
    account.grant(120, "지급", today=date(2026, 11, 11))
    request_id = new_id()
    hold = account.hold(120, request_id=request_id, reason="멘토링 신청")  # 잔여와 같은 값
    assert (hold.type, hold.request_id, account.remaining_minutes, account.held_minutes) == (
        MentoringBalanceTransactionType.HOLD,
        request_id,
        0,
        120,
    )
    with pytest.raises(BusinessRuleViolation) as short:
        account.hold(30, request_id=new_id(), reason="신청")
    assert short.value.code == "insufficient_balance"
    release = account.release(120, request_id=request_id, reason="취소")
    assert (release.type, account.remaining_minutes, account.held_minutes) == (
        MentoringBalanceTransactionType.RELEASE,
        120,
        0,
    )
    with pytest.raises(BusinessRuleViolation):
        account.release(30, request_id=request_id, reason="또")


def test_approve_picks_desired_time_before_start() -> None:
    request = _request(desired_times=[T, T + timedelta(hours=2)])
    now = datetime(2026, 11, 20, 4, 59, tzinfo=UTC)  # 13:59 KST
    with pytest.raises(BusinessRuleViolation) as other:
        request.approve(T + timedelta(hours=1), now=now)
    assert other.value.code == "not_desired_time"
    with pytest.raises(BusinessRuleViolation) as naive:
        request.approve(T.replace(tzinfo=None), now=now)
    assert naive.value.code == "not_desired_time"
    with pytest.raises(BusinessRuleViolation) as passed:  # 시작 시각과 같으면 지난 것
        request.approve(T, now=T)
    assert passed.value.code == "desired_time_passed"

    starts, ends = request.approve(T + timedelta(hours=2), now=now)
    assert (starts, ends - starts) == (T + timedelta(hours=2), timedelta(minutes=60))
    assert request.status is MentoringRequestStatus.APPROVED
    with pytest.raises(BusinessRuleViolation) as again:
        request.approve(T, now=now)
    assert again.value.code == "request_not_pending"
    with pytest.raises(BusinessRuleViolation):
        request.reject("늦음", now=now)


def test_reject_requires_reason() -> None:
    request = _request()
    now = datetime(2026, 11, 11, tzinfo=UTC)
    with pytest.raises(BusinessRuleViolation):
        request.reject(" ", now=now)
    assert request.status is MentoringRequestStatus.PENDING
    request.reject(" 일정이 맞지 않음 ", now=now)
    assert (request.status, request.reject_reason, request.rejected_at) == (
        MentoringRequestStatus.REJECTED,
        "일정이 맞지 않음",
        now,
    )
    with pytest.raises(BusinessRuleViolation):
        request.cancel("취소", now=now)


def test_use_moves_held_to_used() -> None:
    account = BalanceAccount(
        student_id=new_id(), valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
    )
    account.grant(120, "지급", today=date(2026, 11, 11))
    request_id = new_id()
    account.hold(60, request_id=request_id, reason="신청")
    entry = account.use(60, request_id=request_id, reason="승인")
    assert (entry.type, entry.amount, entry.after_remaining, entry.after_held) == (
        MentoringBalanceTransactionType.USING,
        60,
        60,
        0,
    )
    assert (account.used_minutes, account.remaining_minutes) == (60, 60)
    with pytest.raises(BusinessRuleViolation):
        account.use(30, request_id=request_id, reason="승인")


def test_cancel_approved_and_deadline() -> None:
    request = _request()
    now = datetime(2026, 11, 11, tzinfo=UTC)
    request.approve(T, now=now)
    request.cancel("사정이 생김", now=now)
    assert request.status is MentoringRequestStatus.CANCELED

    ensure_before_deadline(T, min_lead_hours=24, now=T - timedelta(hours=24))  # 경계는 허용
    with pytest.raises(BusinessRuleViolation) as late:
        ensure_before_deadline(T, min_lead_hours=24, now=T - timedelta(hours=23, minutes=59))
    assert late.value.code == "cancel_deadline_passed"


def test_refund_moves_used_back() -> None:
    account = BalanceAccount(
        student_id=new_id(), valid_from=date(2026, 11, 1), valid_until=date(2027, 4, 30)
    )
    account.grant(120, "지급", today=date(2026, 11, 11))
    request_id = new_id()
    account.hold(60, request_id=request_id, reason="신청")
    account.use(60, request_id=request_id, reason="승인")
    entry = account.refund(60, request_id=request_id, reason="취소")
    assert (entry.type, account.used_minutes, account.remaining_minutes) == (
        MentoringBalanceTransactionType.REFUND,
        0,
        120,
    )
    with pytest.raises(BusinessRuleViolation):
        account.refund(30, request_id=request_id, reason="취소")

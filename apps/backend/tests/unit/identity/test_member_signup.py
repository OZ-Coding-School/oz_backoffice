from datetime import UTC, datetime
from typing import Any

import pytest

from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.enums import MemberSignupStatus, MemberSignupType
from app.contexts.identity.domain.signup import MemberSignup
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def student(**overrides: Any) -> MemberSignup:
    values: dict[str, Any] = {
        "user_id": new_id(),
        "signup_type": MemberSignupType.STUDENT,
        "requested_cohort_id": new_id(),
    }
    values.update(overrides)
    return MemberSignup(**values)


def mentor(**overrides: Any) -> MemberSignup:
    return MemberSignup(user_id=new_id(), signup_type=MemberSignupType.MENTOR, **overrides)


def test_student_requires_cohort_and_no_mentor_fields() -> None:
    assert student().status is MemberSignupStatus.PENDING
    with pytest.raises(BusinessRuleViolation) as no_cohort:
        student(requested_cohort_id=None)
    assert no_cohort.value.code == "cohort_required"
    with pytest.raises(BusinessRuleViolation) as nickname:
        student(nickname="오즈")
    assert nickname.value.code == "invalid_signup_field"


def test_mentor_fields() -> None:
    plain = mentor(nickname="  ")
    assert (plain.nickname, plain.display_name_preference) == (None, DisplayNamePreference.NAME)
    named = mentor(nickname=" 오즈 ", display_name_preference=DisplayNamePreference.NICKNAME)
    assert named.nickname == "오즈"

    with pytest.raises(BusinessRuleViolation) as cohort:
        mentor(requested_cohort_id=new_id())
    assert cohort.value.code == "invalid_signup_field"
    with pytest.raises(BusinessRuleViolation) as required:
        mentor(display_name_preference=DisplayNamePreference.NICKNAME)
    assert required.value.code == "nickname_required"
    with pytest.raises(BusinessRuleViolation) as too_long:
        mentor(nickname="가" * 31)
    assert too_long.value.code == "invalid_nickname"


def test_review_transitions() -> None:
    approved = student()
    approved.approve(now=NOW)
    assert (approved.status, approved.reviewed_at) == (MemberSignupStatus.APPROVED, NOW)

    rejected = student()
    rejected.reject(" 명단에 없습니다 ", now=NOW)
    assert (rejected.status, rejected.reject_reason) == (
        MemberSignupStatus.REJECTED,
        "명단에 없습니다",
    )

    for done in (approved, rejected):
        with pytest.raises(BusinessRuleViolation) as exc:
            done.approve(now=NOW)
        assert exc.value.code == "signup_not_pending"
    for reason in ("", "가" * 301):
        with pytest.raises(BusinessRuleViolation):
            student().reject(reason, now=NOW)

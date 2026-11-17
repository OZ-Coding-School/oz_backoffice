from datetime import UTC, datetime

import pytest

from app.contexts.identity.domain.entities import OAuthAccount, User
from app.contexts.identity.domain.enums import AccountType, SocialLoginProvider, UserApprovalStatus
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id
from tests.factories.identity import make_user

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def test_new_user_is_pending_and_normalized() -> None:
    user = User(
        email="  Kim@Gmail.COM ",
        name="  김오즈 ",
        account_type=AccountType.MEMBER,
        phone_number="010-1234-5678",
    )
    assert user.email == "kim@gmail.com"
    assert user.name == "김오즈"
    assert user.phone_number == "01012345678"
    assert user.approval_status is UserApprovalStatus.PENDING
    assert not user.is_approved
    assert not user.is_active


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("email", "not-an-email", "invalid_email"),
        ("name", "   ", "invalid_name"),
        ("name", "가" * 51, "invalid_name"),
        ("phone_number", "02-123-4567", "invalid_phone_number"),
        ("phone_number", "010123", "invalid_phone_number"),
    ],
)
def test_invalid_values_are_rejected(field: str, value: str, code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        make_user(**{field: value})
    assert exc.value.code == code


def test_approved_status_requires_approved_at() -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        make_user(approval_status=UserApprovalStatus.APPROVED)
    assert exc.value.code == "invalid_approval_state"


def test_approve_pending_user_activates_account() -> None:
    user = make_user()
    user.approve(now=NOW)
    assert user.is_approved
    assert user.approved_at == NOW
    assert user.is_active


def test_cannot_approve_twice() -> None:
    user = make_user()
    user.approve(now=NOW)
    with pytest.raises(BusinessRuleViolation) as exc:
        user.approve(now=NOW)
    assert exc.value.code == "user_already_approved"


def test_reject_only_pending_and_rejected_can_be_reapproved() -> None:
    user = make_user()
    user.reject()
    assert user.approval_status is UserApprovalStatus.REJECTED
    with pytest.raises(BusinessRuleViolation) as exc:
        user.reject()
    assert exc.value.code == "user_not_pending"

    user.approve(now=NOW)
    assert user.is_approved


def test_verify_phone_normalizes_and_records_time() -> None:
    user = make_user(phone_number=None)
    user.verify_phone("010 9876 5432", now=NOW)
    assert user.phone_number == "01098765432"
    assert user.phone_verified_at == NOW


def test_oauth_account_requires_provider_user_id() -> None:
    with pytest.raises(BusinessRuleViolation):
        OAuthAccount(user_id=new_id(), provider=SocialLoginProvider.GOOGLE, provider_user_id="")


def test_can_login_depends_on_deletion_and_suspension() -> None:
    pending = make_user()
    assert pending.can_login  # 승인 전에는 비활성이어도 상태 확인을 위해 로그인할 수 있다

    approved = make_user()
    approved.approve(now=NOW)
    assert approved.can_login
    approved.deactivate()
    assert not approved.can_login

    deleted = make_user(deleted_at=NOW)
    assert not deleted.can_login


def test_only_rejected_user_can_resubmit() -> None:
    user = make_user()
    with pytest.raises(BusinessRuleViolation) as pending:
        user.resubmit()
    assert pending.value.code == "user_not_rejected"
    user.reject()
    user.resubmit()
    assert user.approval_status is UserApprovalStatus.PENDING

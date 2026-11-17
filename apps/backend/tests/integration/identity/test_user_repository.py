from datetime import UTC, datetime

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.identity.domain.entities import OAuthAccount
from app.contexts.identity.domain.enums import AccountType, SocialLoginProvider, UserApprovalStatus
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from tests.factories.identity import make_user

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


async def test_add_get_and_save_round_trip() -> None:
    repo = TortoiseUserRepository()
    user = make_user(email="Round@Gmail.com")
    await repo.add(user)

    loaded = await repo.get(user.id)
    assert loaded is not None
    assert loaded.email == "round@gmail.com"
    assert loaded.approval_status is UserApprovalStatus.PENDING
    assert loaded.account_type is AccountType.MEMBER

    loaded.approve(now=NOW)
    await repo.save(loaded)
    approved = await repo.get_by_email("ROUND@gmail.com")
    assert approved is not None
    assert approved.is_approved
    assert approved.approved_at == NOW
    assert await repo.get_by_phone(user.phone_number or "") == approved


async def test_email_and_phone_are_unique() -> None:
    repo = TortoiseUserRepository()
    await repo.add(make_user(email="dup@gmail.com", phone_number="01011112222"))
    with pytest.raises(IntegrityError):
        await repo.add(make_user(email="dup@gmail.com"))
    with pytest.raises(IntegrityError):
        await repo.add(make_user(phone_number="01011112222"))


async def test_oauth_account_lookup_and_uniqueness() -> None:
    repo = TortoiseUserRepository()
    user = make_user(email="staff@nextrunners.co.kr")
    await repo.add(user)
    await repo.add_oauth_account(
        OAuthAccount(user_id=user.id, provider=SocialLoginProvider.GOOGLE, provider_user_id="g-1")
    )

    found = await repo.get_by_oauth(SocialLoginProvider.GOOGLE, "g-1")
    assert found == user
    assert await repo.get_by_oauth(SocialLoginProvider.GOOGLE, "g-2") is None

    other = make_user()
    await repo.add(other)
    with pytest.raises(IntegrityError):
        await repo.add_oauth_account(
            OAuthAccount(
                user_id=other.id, provider=SocialLoginProvider.GOOGLE, provider_user_id="g-1"
            )
        )


@pytest.mark.parametrize(
    ("column_sql", "constraint"),
    [
        ("email = 'Upper@gmail.com'", "check_users_email_lowercase"),
        ("approval_status = 'APPROVED'", "check_users_approved_at"),
        ("approval_status = 'UNKNOWN'", "check_users_approval_status"),
        ("phone_number = '0212345678'", "check_users_phone_number"),
        ("account_type = 'ADMIN'", "check_users_account_type"),
    ],
)
async def test_db_check_constraints_reject_invalid_rows(column_sql: str, constraint: str) -> None:
    """앱을 거치지 않은 변경도 DB 제약이 막는다 (raw SQL 마이그레이션 검증)."""
    repo = TortoiseUserRepository()
    user = make_user()
    await repo.add(user)
    with pytest.raises(IntegrityError, match=constraint):
        await connections.get("default").execute_query(
            f"UPDATE users SET {column_sql} WHERE id = $1", [user.id]
        )


async def test_db_defaults_apply_to_raw_insert() -> None:
    conn = connections.get("default")
    await conn.execute_query(
        "INSERT INTO users (id, email, name, account_type) "
        "VALUES (gen_random_uuid(), 'raw@gmail.com', '로우', 'MEMBER')"
    )
    _, rows = await conn.execute_query(
        "SELECT approval_status, is_active, created_at IS NOT NULL AS has_created "
        "FROM users WHERE email = 'raw@gmail.com'"
    )
    assert dict(rows[0]) == {"approval_status": "PENDING", "is_active": False, "has_created": True}

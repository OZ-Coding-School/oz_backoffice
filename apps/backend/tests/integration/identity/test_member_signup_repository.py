"""member_signups 저장 왕복과 DB 제약."""

from datetime import UTC, datetime
from typing import Any

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.enums import MemberSignupStatus, MemberSignupType
from app.contexts.identity.domain.signup import MemberSignup
from app.contexts.identity.infrastructure.models import MemberSignupModel
from app.contexts.identity.infrastructure.repositories import TortoiseMemberSignupRepository
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.educator import create_user

pytestmark = pytest.mark.integration

signups = TortoiseMemberSignupRepository()
NOW = datetime(2026, 11, 9, tzinfo=UTC)


async def test_round_trip_and_latest() -> None:
    user = await create_user()
    cohort = await create_cohort()
    first = MemberSignup(
        user_id=user.id, signup_type=MemberSignupType.STUDENT, requested_cohort_id=cohort.id
    )
    await signups.add(first)
    first.reject("명단 없음", now=NOW)
    await signups.save(first)
    second = MemberSignup(
        user_id=user.id, signup_type=MemberSignupType.STUDENT, requested_cohort_id=cohort.id
    )
    await signups.add(second)  # 반려 후 재신청

    latest = await signups.get_latest_by_user(user.id)
    assert latest is not None
    assert (latest.id, latest.status, latest.created_at is not None) == (
        second.id,
        MemberSignupStatus.PENDING,
        True,
    )
    loaded = await signups.get(first.id)
    assert loaded is not None
    assert loaded.reject_reason == "명단 없음"


async def test_one_pending_signup_per_user() -> None:
    user = await create_user()
    await signups.add(MemberSignup(user_id=user.id, signup_type=MemberSignupType.MENTOR))
    with pytest.raises(IntegrityError):
        await signups.add(MemberSignup(user_id=user.id, signup_type=MemberSignupType.MENTOR))


@pytest.mark.parametrize(
    "values",
    [
        {"signup_type": "STUDENT"},  # 수강생 기수 없음
        {"signup_type": "MENTOR", "requested_cohort": True},  # 멘토 기수 있음
        {"signup_type": "MENTOR", "display_name_preference": "NICKNAME"},  # 닉네임 없음
        {"signup_type": "MENTOR", "status": "APPROVED"},  # 처리 시각 없음
        {"signup_type": "MENTOR", "reject_reason": "x"},  # 대기 중 반려 사유
    ],
)
async def test_db_checks(values: dict[str, Any]) -> None:
    user = await create_user()
    data: dict[str, Any] = {"user_id": user.id, **values}
    if data.pop("requested_cohort", False):
        data["requested_cohort_id"] = (await create_cohort()).id
    with pytest.raises(IntegrityError):
        await MemberSignupModel.create(**data)


async def test_db_defaults() -> None:
    user = await create_user()
    conn = connections.get("default")
    signup_id = new_id()
    await conn.execute_query(
        'INSERT INTO "member_signups" ("id", "user_id", "signup_type", "display_name_preference")'
        " VALUES ($1, $2, 'MENTOR', $3)",
        [signup_id, user.id, DisplayNamePreference.NAME.value],
    )
    _, rows = await conn.execute_query(
        'SELECT "status", "created_at" FROM "member_signups" WHERE "id" = $1', [signup_id]
    )
    assert rows[0]["status"] == "PENDING"
    assert rows[0]["created_at"] is not None

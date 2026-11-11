"""멘토링 시간 계좌 API (실제 DB, A39·A40)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.academy.domain.enums import EnrollmentStatus
from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.ids import new_id
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_user

pytestmark = pytest.mark.api

REGULAR = "REGULAR_MENTORING"


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(new_id())}


async def _approved() -> User:
    user = await create_user()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _setup(client: AsyncClient, settings: Settings) -> dict[str, Any]:
    admin = bearer(
        settings, (await create_super_admin("boss@nextrunners.co.kr", settings=settings)).user
    )
    cohort = await create_cohort()
    await client.put(
        f"/api/v1/admin/cohorts/{cohort.id}/mentoring-settings",
        json={"allow_1_on_1": True, "default_1on1_minutes": 180},
        headers=admin,
    )
    student_user = await _approved()
    repo = TortoiseStudentRepository()
    signed = make_student(cohort_id=cohort.id, name="가수강", user_id=student_user.id)
    pending = make_student(cohort_id=cohort.id, name="나수강")
    dropped = make_student(cohort_id=cohort.id, name="다수강", status=EnrollmentStatus.DROPPED)
    for s in (signed, pending, dropped):
        await repo.add(s)
    return {
        "admin": admin,
        "path": f"/api/v1/admin/cohorts/{cohort.id}/mentoring-balances",
        "student_h": bearer(settings, student_user),
        "signed": signed,
        "pending": pending,
        "dropped": dropped,
    }


async def test_grant_adjust_and_view(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    path, admin = ctx["path"], ctx["admin"]
    body = {"period_type": REGULAR, "target": "ALL_STUDENTS", "reason": "기본 지급"}

    missing_key = await client.post(f"{path}/grants", json=body, headers=admin)
    assert missing_key.status_code == 422
    idem = key()
    granted = await client.post(f"{path}/grants", json=body, headers={**admin, **idem})
    assert granted.status_code == 200, granted.text
    assert len(granted.json()["granted"]) == 2
    replay = await client.post(f"{path}/grants", json=body, headers={**admin, **idem})
    assert replay.json() == granted.json()  # 같은 요청 ID → 다시 지급하지 않음

    accounts = (await client.get(path, headers=admin)).json()
    assert accounts["total"] == 2
    assert {a["owner_name"]: a["remaining_minutes"] for a in accounts["items"]} == {
        "가수강": 180,
        "나수강": 180,
    }

    picked = await client.post(
        f"{path}/grants",
        json={
            "period_type": REGULAR,
            "target": "STUDENTS",
            "ids": [str(ctx["signed"].id), str(ctx["dropped"].id)],
            "minutes": 60,
            "reason": "추가 지급",
        },
        headers={**admin, **key()},
    )
    assert [s["code"] for s in picked.json()["skipped"]] == ["student_not_enrolled"]
    account_id = picked.json()["granted"][0]["account_id"]

    adjusted = await client.post(
        f"{path}/{account_id}/adjustments",
        json={"minutes": -120, "reason": "정정"},
        headers={**admin, **key()},
    )
    assert adjusted.json()["remaining_minutes"] == 120
    too_much = await client.post(
        f"{path}/{account_id}/adjustments",
        json={"minutes": -180, "reason": "초과"},
        headers={**admin, **key()},
    )
    assert too_much.json()["error"]["code"] == "insufficient_balance"
    outside = await client.patch(
        f"{path}/{account_id}",
        json={"valid_from": "2026-10-01", "valid_until": "2026-12-31"},
        headers=admin,
    )
    assert outside.json()["error"]["code"] == "balance_validity_outside_cohort"
    changed = await client.patch(
        f"{path}/{account_id}",
        json={"valid_from": "2026-11-01", "valid_until": "2026-12-31"},
        headers=admin,
    )
    assert changed.json()["valid_until"] == "2026-12-31"

    ledger = (await client.get(f"{path}/{account_id}/transactions", headers=admin)).json()
    assert [(e["type"], e["amount"]) for e in ledger] == [
        ("STAFF_ADJUST", -120),
        ("STAFF_GRANT", 60),
        ("STAFF_GRANT", 180),
    ]
    page = (
        await client.get(
            f"{path}/{account_id}/transactions",
            params={"before": ledger[0]["id"], "limit": 1},
            headers=admin,
        )
    ).json()
    assert [e["amount"] for e in page] == [60]

    mine = (await client.get("/api/v1/me/balances", headers=ctx["student_h"])).json()
    assert [(a["owner_name"], a["remaining_minutes"]) for a in mine] == [("가수강", 120)]
    my_ledger = await client.get(
        f"/api/v1/me/balances/{account_id}/transactions", headers=ctx["student_h"]
    )
    assert len(my_ledger.json()) == 3
    others = next(a for a in accounts["items"] if a["owner_name"] == "나수강")
    hidden = await client.get(
        f"/api/v1/me/balances/{others['id']}/transactions", headers=ctx["student_h"]
    )
    assert hidden.status_code == 404


async def test_permissions(client: AsyncClient, settings: Settings) -> None:
    ctx = await _setup(client, settings)
    path = ctx["path"]
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers=ctx["student_h"])).status_code == 403
    other = f"/api/v1/admin/cohorts/{(await create_cohort()).id}/mentoring-balances"
    assert (await client.get(other, headers=ctx["admin"])).json()["total"] == 0

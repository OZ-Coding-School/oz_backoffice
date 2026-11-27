"""멘토 프로필 API (실제 DB + S3 에뮬레이터 floci)."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.cli import create_super_admin
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.mentoring.domain.assignment import CohortMentor
from app.contexts.mentoring.domain.enums import (
    CohortMentorDeactivationReason,
)
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort
from tests.factories.educator import create_mentor, create_mentor_contract, create_user

pytestmark = pytest.mark.api

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings, s3_bucket: str) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _approved_user(**overrides: Any) -> User:
    user = await create_user(**overrides)
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    return user


async def _upload_image(client: AsyncClient, base: str, h: dict[str, str]) -> httpx.Response:
    ticket = await client.post(
        f"{base}/image/uploads", json={"content_type": "image/png"}, headers=h
    )
    assert ticket.status_code == 201, ticket.text
    data = ticket.json()
    async with httpx.AsyncClient(timeout=10) as s3:
        uploaded = await s3.post(
            data["url"], data=data["fields"], files={"file": ("me.png", PNG, "image/png")}
        )
    assert uploaded.status_code in (200, 201, 204), uploaded.text
    return await client.post(f"{base}/image/uploads/{data['upload_id']}/confirm", headers=h)


async def test_mentor_edits_own_profile_and_image(
    client: AsyncClient, settings: Settings, s3_bucket: str
) -> None:
    user = await _approved_user(name="김멘토")
    await create_mentor(user)
    h = bearer(settings, user)
    base = "/api/v1/me/mentor-profile"

    profile = await client.get(base, headers=h)
    assert profile.status_code == 200, profile.text
    assert (profile.json()["display_name"], profile.json()["profile_image_url"]) == (
        "김멘토",
        None,
    )

    updated = await client.patch(
        base,
        json={"nickname": "오즈", "display_name_preference": "NICKNAME", "headline": "한 줄"},
        headers=h,
    )
    assert updated.json()["display_name"] == "오즈"
    no_nickname = await client.patch(base, json={"nickname": None}, headers=h)
    assert no_nickname.json()["error"]["code"] == "nickname_required"

    confirmed = await _upload_image(client, base, h)
    assert confirmed.status_code == 200, confirmed.text
    async with httpx.AsyncClient(timeout=10) as s3:
        image = await s3.get(confirmed.json()["profile_image_url"])
    assert image.content == PNG

    deleted = await client.delete(f"{base}/image", headers=h)
    assert deleted.json()["profile_image_url"] is None


async def test_non_mentor_and_pending_user(
    client: AsyncClient, settings: Settings, s3_bucket: str
) -> None:
    not_mentor = await _approved_user()
    response = await client.get("/api/v1/me/mentor-profile", headers=bearer(settings, not_mentor))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "mentor_profile_not_found"

    pending = await create_user()
    await create_mentor(pending)
    blocked = await client.get("/api/v1/me/mentor-profile", headers=bearer(settings, pending))
    assert blocked.status_code == 403


async def test_admin_lists_and_edits_mentors(client: AsyncClient, admin: dict[str, str]) -> None:
    mentor = await create_mentor(
        await _approved_user(name="김멘토", email="kim@mentor.com", phone_number="01011112222")
    )
    await create_mentor(await _approved_user(name="박멘토"))

    listed = await client.get("/api/v1/admin/mentors", params={"q": "김멘"}, headers=admin)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    item = listed.json()["items"][0]
    assert (item["id"], item["email"], item["contract_count"]) == (
        str(mentor.id),
        "kim@mentor.com",
        0,
    )
    assert (item["accepting_requests"], item["active_cohorts"]) == (False, [])

    # 활성 배정 기수 (A100): 비활성 배정은 빠진다
    cohort, old = await create_cohort(cohort_number=12), await create_cohort(cohort_number=11)
    repo = TortoiseCohortMentorRepository()
    for c, active in ((cohort, True), (old, False)):
        contract = await create_mentor_contract(
            mentor.id, bootcamp_id=c.bootcamp_id, cohort_id=c.id
        )
        assignment = CohortMentor(
            cohort_id=c.id,
            mentor_id=mentor.id,
            contract_id=contract.id,
            start_date=date(2026, 11, 2),
        )
        if not active:
            assignment.deactivate(CohortMentorDeactivationReason.MANUAL, now=datetime.now(UTC))
        await repo.add(assignment)
    item = (await client.get("/api/v1/admin/mentors", params={"q": "김멘"}, headers=admin)).json()[
        "items"
    ][0]
    assert [(c["cohort_id"], c["cohort_number"]) for c in item["active_cohorts"]] == [
        (str(cohort.id), 12)
    ]

    # 단건 (A102): 목록 항목과 같은 응답
    one = await client.get(f"/api/v1/admin/mentors/{mentor.id}", headers=admin)
    assert one.status_code == 200
    assert one.json() == item
    missing = await client.get(f"/api/v1/admin/mentors/{uuid.uuid4()}", headers=admin)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "mentor_not_found")

    base = f"/api/v1/admin/mentors/{mentor.id}/profile"
    edited = await client.patch(base, json={"expertise": "백엔드"}, headers=admin)
    assert edited.json()["expertise"] == "백엔드"
    confirmed = await _upload_image(client, base, admin)
    assert confirmed.json()["profile_image_url"] is not None


async def test_admin_requires_contract_manage(
    client: AsyncClient, settings: Settings, s3_bucket: str
) -> None:
    assert (await client.get("/api/v1/admin/mentors")).status_code == 401
    member = await _approved_user()
    forbidden = await client.get("/api/v1/admin/mentors", headers=bearer(settings, member))
    assert forbidden.status_code == 403
    one = await client.get(
        f"/api/v1/admin/mentors/{uuid.uuid4()}", headers=bearer(settings, member)
    )
    assert one.status_code == 403

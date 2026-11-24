"""명단 동기화 API (실제 DB, 가짜 작업 전달자)."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr

from app.cli import create_super_admin
from app.contexts.academy.domain.entities import Bootcamp, Cohort, RosterSyncRun
from app.contexts.academy.domain.enums import RosterSyncScope, RosterSyncTrigger
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseRosterSyncRunRepository,
    TortoiseStudentRepository,
)
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings
from app.core.security import JWTService
from tests.factories.academy import create_cohort, make_student
from tests.factories.access import ASSISTANT, give_role
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.api

API = "/api/v1/admin"


class FakeDispatcher:
    def __init__(self) -> None:
        self.sent: list[uuid.UUID] = []
        self.fail = False

    async def dispatch(self, run_id: uuid.UUID) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.sent.append(run_id)


@pytest.fixture
def dispatcher(app: FastAPI, settings: Settings) -> FakeDispatcher:
    fake = FakeDispatcher()
    app.state.roster_sync_dispatcher = fake
    app.state.settings = settings.model_copy(
        update={
            "airtable_token": SecretStr("pat-test"),
            "airtable_base_id": "appTEST",
            "airtable_student_table_id": "tblSTUDENT",
            "airtable_bootcamp_table_id": "tblBOOTCAMP",
        }
    )
    return fake


def bearer(settings: Settings, user: User) -> dict[str, str]:
    token, _ = JWTService(settings).encode(str(user.id), "access", now=datetime.now(UTC))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin(settings: Settings) -> dict[str, str]:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    return bearer(settings, result.user)


async def _syncable_cohort(prefix: str = "헬스케어") -> tuple[Bootcamp, Cohort]:
    cohort = await create_cohort()
    bootcamps = TortoiseBootcampRepository()
    bootcamp = await bootcamps.get(cohort.bootcamp_id)
    assert bootcamp is not None
    bootcamp.airtable_cohort_prefix = prefix
    await bootcamps.save(bootcamp)
    return bootcamp, cohort


async def _assistant(settings: Settings, cohort: Cohort) -> dict[str, str]:
    user = await create_applicant()
    user.approve(now=datetime.now(UTC))
    await TortoiseUserRepository().save(user)
    await give_role(user.id, ASSISTANT, cohort_id=cohort.id)
    return bearer(settings, user)


async def test_manual_sync_is_dispatched_and_locked(
    client: AsyncClient, admin: dict[str, str], dispatcher: FakeDispatcher
) -> None:
    bootcamp, cohort = await _syncable_cohort()

    accepted = await client.post(f"{API}/cohorts/{cohort.id}/rosters/sync", headers=admin)

    assert accepted.status_code == 202
    body = accepted.json()
    assert (body["status"], body["scope_type"], body["bootcamp_id"]) == (
        "RUNNING",
        "COHORT",
        str(bootcamp.id),
    )
    assert dispatcher.sent == [uuid.UUID(body["id"])]
    busy = await client.post(f"{API}/bootcamps/{bootcamp.id}/rosters/sync", headers=admin)
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "roster_sync_in_progress")
    status = await client.get(f"{API}/rosters/sync-runs/{body['id']}", headers=admin)
    assert status.json()["status"] == "RUNNING"


async def test_dispatch_failure_aborts_run(
    client: AsyncClient, admin: dict[str, str], dispatcher: FakeDispatcher
) -> None:
    bootcamp, _ = await _syncable_cohort()
    dispatcher.fail = True
    failed = await client.post(f"{API}/bootcamps/{bootcamp.id}/rosters/sync", headers=admin)
    assert (failed.status_code, failed.json()["error"]["code"]) == (
        503,
        "roster_sync_dispatch_failed",
    )
    dispatcher.fail = False
    # 실행은 실패로 끝났고 락도 풀려 다시 요청할 수 있다
    runs = (await client.get(f"{API}/rosters/sync-runs", headers=admin)).json()["items"]
    assert runs[0]["status"] == "FAILED"
    retry = await client.post(f"{API}/bootcamps/{bootcamp.id}/rosters/sync", headers=admin)
    assert retry.status_code == 202


async def test_validation_errors(
    client: AsyncClient,
    admin: dict[str, str],
    dispatcher: FakeDispatcher,
    settings: Settings,
    app: FastAPI,
) -> None:
    # 별칭이 없는 과정도 요청은 받는다.
    # 과정-기수 테이블 동기화로 별칭이 채워지지 않으면 실행이 실패한다
    no_prefix = await create_cohort()
    accepted = await client.post(f"{API}/cohorts/{no_prefix.id}/rosters/sync", headers=admin)
    assert accepted.status_code == 202
    app.state.settings = settings  # Airtable 미설정
    unconfigured = await client.post(f"{API}/rosters/sync", headers=admin)
    assert (unconfigured.status_code, unconfigured.json()["error"]["code"]) == (
        503,
        "airtable_not_configured",
    )
    assert len(dispatcher.sent) == 1


async def test_assistant_scope(
    client: AsyncClient, settings: Settings, dispatcher: FakeDispatcher, admin: dict[str, str]
) -> None:
    _, own = await _syncable_cohort("BD")
    other_bootcamp, other = await _syncable_cohort("UD")
    assistant = await _assistant(settings, own)

    assert (
        await client.post(f"{API}/cohorts/{own.id}/rosters/sync", headers=assistant)
    ).status_code == 202
    assert (
        await client.post(f"{API}/cohorts/{other.id}/rosters/sync", headers=assistant)
    ).status_code == 403
    assert (await client.post(f"{API}/rosters/sync", headers=assistant)).status_code == 403
    assert (await client.get(f"{API}/rosters/unmapped", headers=assistant)).status_code == 403

    # 관리자가 다른 과정 동기화를 실행해도 조교에게는 자기 기수 실행만 보인다
    other_run = (
        await client.post(f"{API}/bootcamps/{other_bootcamp.id}/rosters/sync", headers=admin)
    ).json()
    visible = (await client.get(f"{API}/rosters/sync-runs", headers=assistant)).json()["items"]
    assert [r["cohort_id"] for r in visible] == [str(own.id)]
    hidden = await client.get(f"{API}/rosters/sync-runs/{other_run['id']}", headers=assistant)
    assert hidden.status_code == 404
    assert len((await client.get(f"{API}/rosters/sync-runs", headers=admin)).json()["items"]) == 2


async def test_cohort_roster_and_unmapped(
    client: AsyncClient, admin: dict[str, str], settings: Settings
) -> None:
    _, cohort = await _syncable_cohort()
    students = TortoiseStudentRepository()
    joined = await create_applicant()
    await students.add(make_student(cohort_id=cohort.id, name="가입자", user_id=joined.id))
    await students.add(make_student(cohort_id=cohort.id, name="미가입자"))
    await students.add(make_student(cohort_id=cohort.id, name="삭제됨", is_removed_in_source=True))
    run = RosterSyncRun(
        trigger=RosterSyncTrigger.SCHEDULED,
        scope_type=RosterSyncScope.ALL,
        started_at=datetime.now(UTC),
    )
    await TortoiseRosterSyncRunRepository().add(run)
    run.succeed(
        now=datetime.now(UTC),
        fetched=3,
        upserted=2,
        removed=0,
        unmapped_records=[{"airtable_record_id": "recX", "reason": "cohort_not_found"}],
    )
    await TortoiseRosterSyncRunRepository().save(run)
    assistant = await _assistant(settings, cohort)
    url = f"{API}/cohorts/{cohort.id}/rosters"

    names = [s["name"] for s in (await client.get(url, headers=assistant)).json()]
    assert names == ["가입자", "미가입자"]
    unclaimed = (await client.get(url, params={"claimed": False}, headers=assistant)).json()
    assert [s["name"] for s in unclaimed] == ["미가입자"]
    every = (await client.get(url, params={"include_removed": True}, headers=admin)).json()
    assert len(every) == 3

    unmapped = (await client.get(f"{API}/rosters/unmapped", headers=admin)).json()
    assert (unmapped["run_id"], unmapped["records"][0]["airtable_record_id"]) == (
        str(run.id),
        "recX",
    )

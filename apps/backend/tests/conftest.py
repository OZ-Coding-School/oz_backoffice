"""공용 픽스처.

- unit: 외부 의존 없음
- api: create_app() + httpx ASGITransport.
  lifespan을 돌리지 않으므로 Redis/DB 의존성은 오버라이드한다.
- integration: 실제 PostgreSQL 필요. TEST_DATABASE_URL이 없으면 skip.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from aerich import Command
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.health import get_database_probe
from app.core.config import Settings
from app.core.database import MODEL_APP, build_tortoise_config
from app.core.redis import get_redis
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        environment="test",
        database_url=TEST_DATABASE_URL or "postgres://unused:unused@localhost:5432/unused",
        jwt_secret_key="test-secret-key-with-enough-length-0123456789",
    )


# ----------------------------------------------
# API
# ----------------------------------------------
@pytest.fixture
async def fake_redis() -> AsyncIterator[FakeAsyncRedis]:
    redis = FakeAsyncRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()


@pytest.fixture
def app(settings: Settings, fake_redis: FakeAsyncRedis) -> Iterator[FastAPI]:
    application = create_app(settings)

    async def _db_ok() -> None:
        return None

    application.dependency_overrides[get_redis] = lambda: fake_redis
    application.dependency_overrides[get_database_probe] = lambda: _db_ok
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


# ----------------------------------------------
# Integration (PostgreSQL)
# ----------------------------------------------
async def _reset_schema_and_migrate(database_url: str) -> None:
    """테스트 DB를 비우고 aerich 마이그레이션을 처음부터 적용한다 (raw SQL 제약 포함)."""
    config = build_tortoise_config(database_url)
    # aerich는 Tortoise가 이미 초기화돼 있으면 그 연결을 쓴다.
    # Tortoise 1.x 기본값(전역 연결 없음)으로 aerich가 직접 초기화하면 연결을 찾지 못하므로,
    # 전역 연결 모드로 먼저 초기화해 둔다.
    await Tortoise.init(config=config, _enable_global_fallback=True)
    try:
        await Tortoise.get_connection("default").execute_script(
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public; "
            "CREATE EXTENSION IF NOT EXISTS btree_gist;"
        )
        command = Command(tortoise_config=config, app=MODEL_APP, location=str(MIGRATIONS_DIR))
        await command.init()
        await command.upgrade(run_in_transaction=True)
    finally:
        await Tortoise.close_connections()


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[None]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL이 설정되지 않아 통합 테스트를 건너뜁니다.")
    await _reset_schema_and_migrate(TEST_DATABASE_URL)
    await Tortoise.init(
        config=build_tortoise_config(TEST_DATABASE_URL, with_aerich=False),
        _enable_global_fallback=True,
    )
    yield
    await Tortoise.close_connections()


@pytest.fixture
async def db(database: None) -> AsyncIterator[None]:
    """테스트마다 모델 테이블을 비워 격리한다 (aerich 이력 테이블 제외)."""
    yield
    tables = sorted(
        model._meta.db_table
        for model in Tortoise.apps[MODEL_APP].values()
        if model._meta.db_table != "aerich"
    )
    if tables:
        quoted = ", ".join(f'"{table}"' for table in tables)
        await Tortoise.get_connection("default").execute_script(
            f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"
        )

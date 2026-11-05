"""공용 픽스처.

- unit: 외부 의존 없음
- api: create_app() + httpx ASGITransport.
  lifespan을 돌리지 않으므로 Redis/DB 의존성은 오버라이드한다.
- integration: 실제 PostgreSQL 필요. TEST_DATABASE_URL이 없으면 skip.
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.health import get_database_probe
from app.core.config import Settings
from app.core.database import build_tortoise_config
from app.core.redis import get_redis
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


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
@pytest.fixture(scope="session")
async def database() -> AsyncIterator[None]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL이 설정되지 않아 통합 테스트를 건너뜁니다.")
    await Tortoise.init(
        config=build_tortoise_config(TEST_DATABASE_URL, with_aerich=False),
        _create_db=False,
        _enable_global_fallback=True,
    )
    # TODO: 모델이 생기면 aerich 마이그레이션 적용으로 교체 (EXCLUDE 등 raw SQL 제약 포함)
    await Tortoise.generate_schemas(safe=True)
    yield
    await Tortoise.close_connections()

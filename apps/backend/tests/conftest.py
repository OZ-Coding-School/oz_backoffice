"""공용 픽스처.

- unit: 외부 의존 없음
- api: create_app() + httpx ASGITransport.
  lifespan을 돌리지 않으므로 Redis/DB 의존성은 오버라이드한다.
- integration: 실제 PostgreSQL 사용.

DB는 모든 테스트에 autouse로 준비한다(세션당 1회 생성·마이그레이션, 테스트마다 TRUNCATE).
테스트 DB 주소는 TEST_DATABASE_URL(compose·CI가 설정), 없으면 로컬 compose의 postgres를 쓴다.
"""

import importlib.util
import os
import warnings
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit

import asyncpg  # type: ignore[import-untyped]
import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import connections
from tortoise.context import TortoiseContext
from tortoise.warnings import TortoiseLoopSwitchWarning

from app.api.health import get_database_probe
from app.core.config import Settings
from app.core.database import MODEL_APP, build_tortoise_config
from app.core.redis import get_redis
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgres://oz:oz@localhost:5432/oz_backoffice_test"
)
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture(scope="session")
def settings() -> Settings:
    # 개발자 로컬 .env와 compose env_file(DEBUG, GOOGLE_* 등)이 테스트 결과를 바꾸지 않도록
    # .env는 읽지 않고, 환경변수로 들어오는 값 중 결과에 영향을 주는 것은 직접 고정한다
    return Settings(
        _env_file=None,
        environment="test",
        debug=False,
        google_client_id="",
        google_client_secret="",
        google_redirect_uri="http://localhost:5173/auth/google/callback",
        google_allowed_domain="nextrunners.co.kr",
        refresh_cookie_secure=True,
        # 실제 Airtable 자격 증명을 테스트에서 쓰지 않는다
        airtable_token="",
        airtable_base_id="",
        airtable_student_table_id="",
        airtable_bootcamp_table_id="",
        database_url=TEST_DATABASE_URL,
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
# DB (PostgreSQL)
# ----------------------------------------------
async def _admin_execute(sql: str) -> str:
    """관리 DB(postgres)에 접속해 테스트 DB를 만들거나 지운다. 실행한 DB 이름을 돌려준다.

    이름이 `_test`로 끝나지 않으면 거부한다 (개발·운영 DB 보호).
    Tortoise의 _create_db는 사용자 이름과 같은 DB로 접속하므로 쓰지 않는다.
    """
    url = urlsplit(TEST_DATABASE_URL)
    name = url.path.lstrip("/")
    if not name.endswith("_test"):
        raise RuntimeError(f"테스트 DB 이름은 _test로 끝나야 합니다: {name!r}")
    conn = await asyncpg.connect(
        host=url.hostname,
        port=url.port or 5432,
        user=unquote(url.username or ""),
        password=unquote(url.password or ""),
        database="postgres",
    )
    try:
        await conn.execute(sql.format(name=name))
    finally:
        await conn.close()
    return name


async def _drop_test_database() -> None:
    await _admin_execute('DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


async def _create_test_database() -> None:
    await _admin_execute('CREATE DATABASE "{name}"')


def _migration_modules() -> list[ModuleType]:
    """aerich 마이그레이션 파일을 번호 순서대로 불러온다.

    파일 이름이 숫자로 시작해 import 문으로는 불러올 수 없다.
    """
    paths = sorted(
        (MIGRATIONS_DIR / MODEL_APP).glob("[0-9]*_*.py"),
        key=lambda path: int(path.name.split("_", 1)[0]),
    )
    modules = []
    for path in paths:
        spec = importlib.util.spec_from_file_location(f"_migration_{path.stem}", path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


async def _apply_migrations() -> None:
    """generate_schemas() 대신 aerich 마이그레이션 SQL로 스키마를 만든다.

    마이그레이션에만 있는 raw SQL(CHECK, 부분 유니크, NULLS NOT DISTINCT, 자기 참조 FK,
    DB 기본값)까지 운영과 같은 스키마로 테스트하기 위해서다.
    """
    conn = connections.get("default")
    await conn.execute_script("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    for module in _migration_modules():
        await conn.execute_script(await module.upgrade(conn))


@pytest.fixture(scope="session", autouse=True)
async def tortoise_db() -> AsyncIterator[TortoiseContext]:
    """세션 동안 쓰는 격리된 Tortoise 컨텍스트와 테스트 전용 DB.

    tortoise_test_context(https://tortoise.github.io/contrib/unittest.html)와 같은 방식으로
    격리된 TortoiseContext를 연다(전역 연결 없음). 다만 tortoise_test_context는
    generate_schemas()를 강제하므로, 스키마는 마이그레이션으로 만든다.
    테스트 DB는 세션 시작 때 지우고 새로 만들고, 끝나면 지운다
    (이전 실행이 중단돼 남은 DB·스키마가 결과에 섞이지 않게 한다).
    """
    await _drop_test_database()
    await _create_test_database()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=TortoiseLoopSwitchWarning)
        async with TortoiseContext() as ctx:
            await ctx.init(config=build_tortoise_config(TEST_DATABASE_URL, with_aerich=False))
            await _apply_migrations()
            yield ctx
    await _drop_test_database()


@pytest.fixture(autouse=True)
async def clean_tables(tortoise_db: TortoiseContext) -> AsyncIterator[None]:
    """테스트마다 끝난 뒤 모든 모델 테이블을 비워 테스트 간 데이터가 섞이지 않게 한다."""
    yield
    apps = tortoise_db.apps
    assert apps is not None
    tables = sorted(model._meta.db_table for model in apps[MODEL_APP].values())
    quoted = ", ".join(f'"{table}"' for table in tables)
    await connections.get("default").execute_script(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")

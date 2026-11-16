"""공용 픽스처.

- unit: 외부 의존 없음
- api: create_app() + httpx ASGITransport.
  lifespan을 돌리지 않으므로 Redis/DB 의존성은 오버라이드한다.
- integration: 실제 PostgreSQL 사용. S3 테스트는 에뮬레이터(floci)의 테스트 버킷 사용.

DB는 모든 테스트에 autouse로 준비한다(세션당 1회 생성·마이그레이션, 테스트마다 TRUNCATE).
테스트 DB 주소는 TEST_DATABASE_URL(compose·CI가 설정), 없으면 로컬 compose의 postgres를 쓴다.
"""

import asyncio
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
from app.contexts.mentoring.infrastructure.chat_events import RedisChatEvents
from app.core.config import Settings, get_settings
from app.core.database import MODEL_APP, build_tortoise_config
from app.core.redis import get_redis
from app.main import create_app
from tests.fakes.mentoring import RecordingMeetScheduler
from tests.fakes.notifications import InMemoryMailDispatcher
from tests.s3_bucket import provision_test_bucket

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgres://oz:oz@localhost:5432/oz_backoffice_test"
)
# S3 통합 테스트는 에뮬레이터(floci)의 테스트 전용 버킷을 쓴다 (tests/integration/storage)
TEST_S3_ENDPOINT_URL = os.environ.get("TEST_S3_ENDPOINT_URL", "http://localhost:4566")
TEST_S3_BUCKET = "oz-backoffice-test"
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
        # 실제 메일·SMS를 보내지 않는다
        mail_driver="console",
        sms_driver="console",
        gmail_sender="",
        google_service_account_json="",
        # 개발 버킷(compose S3_*)이 아니라 테스트 전용 버킷을 쓴다
        aws_region="ap-northeast-2",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        s3_bucket=TEST_S3_BUCKET,
        s3_endpoint_url=TEST_S3_ENDPOINT_URL,
        s3_public_endpoint_url=TEST_S3_ENDPOINT_URL,
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


@pytest.fixture(autouse=True)
def _no_external_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """로컬 .env에 실제 Google 설정이 있어도 테스트가 외부 API를 부르지 않게 한다.

    작업(worker) 코드는 get_settings()로 .env를 읽으므로, 환경 변수로 개발용 드라이버를 강제하고
    캐시를 비운다(환경 변수가 .env보다 우선).
    """
    monkeypatch.setenv("MEET_DRIVER", "disabled")
    monkeypatch.setenv("MAIL_DRIVER", "console")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def app(settings: Settings, fake_redis: FakeAsyncRedis) -> Iterator[FastAPI]:
    application = create_app(settings)

    async def _db_ok() -> None:
        return None

    # 알림 메일을 실제 워커 큐로 보내지 않는다
    application.state.mail_dispatcher = InMemoryMailDispatcher()
    application.state.meet_scheduler = (
        RecordingMeetScheduler()
    )  # Meet 공간 생성 작업도 보내지 않는다
    application.dependency_overrides[get_redis] = lambda: fake_redis
    application.state.chat_events = RedisChatEvents(fake_redis)  # lifespan을 돌리지 않으므로
    application.dependency_overrides[get_database_probe] = lambda: _db_ok
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture(scope="session")
async def s3_bucket(settings: Settings) -> AsyncIterator[str]:
    """S3 에뮬레이터(floci)의 테스트 전용 버킷. S3를 쓰는 테스트만 요청한다."""
    async with provision_test_bucket(settings) as bucket:
        yield bucket


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


# 세션 끝 DROP 도중 CI의 PostgreSQL이 연결을 끊거나 서버 프로세스를 재시작(recovery mode)하는
# 일이 가끔 있다. recovery 중 연결은 CannotConnectNowError(PostgresConnectionError 아님)로 온다.
_DROP_RETRY_ERRORS = (
    asyncpg.InterfaceError,
    asyncpg.PostgresConnectionError,
    asyncpg.CannotConnectNowError,
    OSError,
)
_DROP_ATTEMPTS = 4


async def _drop_test_database_at_exit() -> None:
    """세션 끝 정리. 연결 오류·recovery 중이면 잠시 기다려 다시 시도하고(테스트 결과와 무관),
    끝내 실패하면 경고만 남긴다. 다음 세션은 시작할 때 DB를 지우고 새로 만들므로
    남은 DB가 결과에 섞이지 않는다."""
    for attempt in range(1, _DROP_ATTEMPTS + 1):
        try:
            await _drop_test_database()
            return
        except _DROP_RETRY_ERRORS as exc:
            if attempt == _DROP_ATTEMPTS:
                warnings.warn(f"테스트 DB 정리 실패(다음 세션이 지움): {exc!r}", stacklevel=1)
                return
            await asyncio.sleep(attempt)


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
    await _drop_test_database_at_exit()


@pytest.fixture(autouse=True)
async def clean_tables(tortoise_db: TortoiseContext) -> AsyncIterator[None]:
    """테스트마다 끝난 뒤 모든 모델 테이블을 비워 테스트 간 데이터가 섞이지 않게 한다."""
    yield
    apps = tortoise_db.apps
    assert apps is not None
    tables = sorted(model._meta.db_table for model in apps[MODEL_APP].values())
    quoted = ", ".join(f'"{table}"' for table in tables)
    await connections.get("default").execute_script(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")

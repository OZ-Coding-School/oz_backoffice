"""FastAPI 애플리케이션 팩토리."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import health, v1
from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.database import build_tortoise_config
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.redis import create_redis


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.redis = create_redis(settings.redis_url)
        app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            async with RegisterTortoise(
                app,
                config=build_tortoise_config(settings.database_url, with_aerich=False),
            ):
                yield
        finally:
            await app.state.http_client.aclose()
            await app.state.redis.aclose()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.clock = SystemClock()
    # 컨텍스트 간 공개 서비스 연결 (composition root). 다른 컨텍스트의 presentation 의존성이
    # 이 서비스를 쓰되 identity.infrastructure를 직접 import하지 않게 한다.
    app.state.user_queries = UserQueries(TortoiseUserRepository())
    app.state.academy_catalog = AcademyCatalog(
        TortoiseBootcampRepository(), TortoiseCohortRepository()
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(v1.router, prefix=settings.api_prefix)
    return app


app = create_app()

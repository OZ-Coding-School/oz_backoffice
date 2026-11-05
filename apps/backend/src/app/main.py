"""FastAPI 애플리케이션 팩토리."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import health, v1
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
        try:
            async with RegisterTortoise(
                app,
                config=build_tortoise_config(settings.database_url, with_aerich=False),
            ):
                yield
        finally:
            await app.state.redis.aclose()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings

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

"""앱 공통 FastAPI 의존성: 설정, 시계, 외부 HTTP 클라이언트.

값은 create_app()·lifespan이 app.state에 올려 둔다. 테스트는 app.state 값을 바꾸거나 오버라이드한다.
"""

from typing import cast

import httpx
from fastapi import Request

from app.core.clock import Clock
from app.core.config import Settings
from app.core.security import JWTService


def get_app_settings(request: Request) -> Settings:
    return cast("Settings", request.app.state.settings)


def get_clock(request: Request) -> Clock:
    return cast("Clock", request.app.state.clock)


def get_jwt_service(request: Request) -> JWTService:
    return JWTService(get_app_settings(request))


def get_http_client(request: Request) -> httpx.AsyncClient:
    """외부 API 호출용 공유 클라이언트 (lifespan에서 생성, 연결 재사용)."""
    return cast("httpx.AsyncClient", request.app.state.http_client)

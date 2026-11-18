"""CORS: 프론트(다른 출처)가 읽어야 하는 응답 헤더 (decisions F21)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api

FRONTEND = "http://localhost:5173"


async def test_retry_after_is_exposed_to_frontend(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": FRONTEND})
    assert response.headers["access-control-allow-origin"] == FRONTEND
    assert response.headers["access-control-allow-credentials"] == "true"
    exposed = [
        h.strip().lower() for h in response.headers["access-control-expose-headers"].split(",")
    ]
    assert "retry-after" in exposed


async def test_unknown_origin_gets_no_cors_headers(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers

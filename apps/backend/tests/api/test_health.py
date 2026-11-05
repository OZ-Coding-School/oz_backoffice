import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.health import get_database_probe

pytestmark = pytest.mark.api


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_readiness_reports_database_failure(app: FastAPI, client: AsyncClient) -> None:
    async def _db_down() -> None:
        raise ConnectionError("db down")

    app.dependency_overrides[get_database_probe] = lambda: _db_down

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "error", "redis": "ok"}

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError

pytestmark = pytest.mark.api


@pytest.fixture
def app_with_error_routes(app: FastAPI) -> FastAPI:
    @app.get("/_test/not-found")
    async def not_found() -> None:
        raise NotFoundError("신청을 찾을 수 없습니다.", code="mentoring_request_not_found")

    @app.get("/_test/rule")
    async def rule() -> None:
        raise BusinessRuleViolation("잔여 시간이 부족합니다.", code="insufficient_balance")

    @app.get("/_test/forbidden")
    async def forbidden() -> None:
        raise PermissionDeniedError("권한이 없습니다.")

    @app.get("/_test/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    return app


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/_test/not-found", 404, "mentoring_request_not_found"),
        ("/_test/rule", 422, "insufficient_balance"),
        ("/_test/forbidden", 403, "permission_denied"),
        ("/_test/crash", 500, "internal_error"),
    ],
)
async def test_errors_are_mapped_to_http(
    app_with_error_routes: FastAPI, client: AsyncClient, path: str, status: int, code: str
) -> None:
    response = await client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_integrity_error_is_mapped_to_conflict(app: FastAPI, client: AsyncClient) -> None:
    from tortoise.exceptions import IntegrityError

    @app.get("/_test/integrity")
    async def integrity() -> None:
        raise IntegrityError("duplicate key")

    response = await client.get("/_test/integrity")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"

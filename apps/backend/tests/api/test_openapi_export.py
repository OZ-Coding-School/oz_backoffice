"""OpenAPI 스키마 내보내기 (프론트 타입 생성용, decisions F19)."""

import json

import pytest

from app.cli import export_openapi, main
from app.core.config import Settings

pytestmark = pytest.mark.api


def test_export_openapi_is_stable_json(settings: Settings) -> None:
    exported = export_openapi(settings)
    assert exported.endswith("\n")
    schema = json.loads(exported)
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/auth/refresh" in schema["paths"]
    # 같은 앱이면 항상 같은 결과다 (CI가 커밋된 파일과 비교한다)
    assert export_openapi(settings) == exported


def test_cli_prints_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["export-openapi"]) == 0
    assert "/api/v1/me" in json.loads(capsys.readouterr().out)["paths"]

"""Airtable 읽기 클라이언트 (pyairtable, decisions B11).

- pyairtable이 페이지네이션(offset)과 429 재시도(기본 재시도 정책, 백오프)를 처리한다.
- pyairtable은 동기(requests) 라이브러리라 이벤트 루프를 막지 않도록 `asyncio.to_thread`로 호출한다.
- HTTP 오류·연결 오류는 `AirtableError`(503)로 바꿔 올린다.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from pyairtable import Api

from app.shared.errors import ServiceUnavailableError

# (연결, 읽기) 타임아웃 초. 큰 테이블도 페이지당 100건이라 읽기 30초면 충분하다
DEFAULT_TIMEOUT = (10, 30)


@dataclass(frozen=True, slots=True)
class AirtableRecord:
    id: str
    fields: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AirtableField:
    name: str
    type: str


class AirtableError(ServiceUnavailableError):
    default_code = "airtable_unavailable"


def quote_formula_value(value: str) -> str:
    """filterByFormula 문자열 리터럴. 역슬래시·작은따옴표를 이스케이프한다."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def field_ref(name: str) -> str:
    """필드 참조 `{필드명}`. 필드명에 중괄호가 있으면 수식이 깨지므로 거부한다."""
    if "{" in name or "}" in name:
        raise ValueError(f"필드명에 중괄호를 쓸 수 없습니다: {name}")
    return f"{{{name}}}"


class AirtableClient:
    def __init__(self, *, token: str, base_id: str, api: Api | None = None) -> None:
        self._api = api or Api(token, timeout=DEFAULT_TIMEOUT)
        self._base_id = base_id

    async def list_records(
        self, table: str, *, formula: str | None = None, fields: list[str] | None = None
    ) -> list[AirtableRecord]:
        options: dict[str, Any] = {}
        if formula:
            options["formula"] = formula
        if fields:
            options["fields"] = fields
        target = self._api.table(self._base_id, table)
        rows = await self._call(lambda: target.all(**options))
        return [AirtableRecord(id=row["id"], fields=dict(row.get("fields", {}))) for row in rows]

    async def list_fields(self, table: str) -> list[AirtableField]:
        """테이블의 필드 정의 (메타데이터 API, schema.bases:read 범위 필요)."""
        base = self._api.base(self._base_id)
        schema = await self._call(lambda: base.schema().table(table))
        return [AirtableField(name=f.name, type=f.type) for f in schema.fields]

    async def _call[T](self, func: Callable[[], T]) -> T:
        try:
            return await asyncio.to_thread(func)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            raise AirtableError(
                f"Airtable 요청이 실패했습니다 (HTTP {status}).", code="airtable_request_failed"
            ) from exc
        except requests.RequestException as exc:
            raise AirtableError("Airtable에 연결할 수 없습니다.") from exc

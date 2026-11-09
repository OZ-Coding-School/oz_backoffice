"""Airtable 클라이언트 래퍼. HTTP 동작(페이지네이션·429 재시도)은 pyairtable이 담당하므로,
여기서는 호출 인자 전달·응답 변환·오류 변환을 가짜 pyairtable 객체로 검증한다."""

from typing import Any

import pytest
import requests

from app.integrations.airtable.client import (
    AirtableClient,
    AirtableError,
    field_ref,
    quote_formula_value,
)

pytestmark = pytest.mark.unit


class FakeTable:
    def __init__(self, rows: list[dict[str, Any]] | Exception) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def all(self, **options: Any) -> list[dict[str, Any]]:
        self.calls.append(options)
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


class FakeField:
    def __init__(self, name: str, type_: str) -> None:
        self.name, self.type = name, type_


class FakeSchema:
    def __init__(self, fields: list[FakeField]) -> None:
        self.fields = fields

    def table(self, name: str) -> "FakeSchema":
        return self


class FakeBase:
    def schema(self) -> FakeSchema:
        return FakeSchema(
            [FakeField("이름", "singleLineText"), FakeField("기수", "multipleLookupValues")]
        )


class FakeApi:
    def __init__(self, table: FakeTable) -> None:
        self._table = table
        self.opened: list[tuple[str, str]] = []

    def table(self, base_id: str, name: str) -> FakeTable:
        self.opened.append((base_id, name))
        return self._table

    def base(self, base_id: str) -> FakeBase:
        return FakeBase()


def make_client(table: FakeTable) -> tuple[AirtableClient, FakeApi]:
    api = FakeApi(table)
    return AirtableClient(token="pat", base_id="appBASE", api=api), api  # type: ignore[arg-type]


def test_formula_helpers_escape() -> None:
    assert quote_formula_value("헬스케어 3기") == "'헬스케어 3기'"
    assert quote_formula_value("a'b\\c") == "'a\\'b\\\\c'"
    assert field_ref("HRD상태") == "{HRD상태}"
    with pytest.raises(ValueError, match="중괄호"):
        field_ref("bad}name")


async def test_list_records_passes_formula_and_fields() -> None:
    table = FakeTable(
        [{"id": "rec1", "createdTime": "x", "fields": {"이름": "김오즈"}}, {"id": "rec2"}]
    )
    client, api = make_client(table)

    records = await client.list_records(
        "수강생 정보 시트", formula="{기수}='헬스케어 3기'", fields=["이름"]
    )

    assert api.opened == [("appBASE", "수강생 정보 시트")]
    assert table.calls == [{"formula": "{기수}='헬스케어 3기'", "fields": ["이름"]}]
    assert [(r.id, r.fields) for r in records] == [("rec1", {"이름": "김오즈"}), ("rec2", {})]


async def test_list_records_without_options() -> None:
    table = FakeTable([])
    client, _ = make_client(table)
    assert await client.list_records("t") == []
    assert table.calls == [{}]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            requests.HTTPError(response=type("R", (), {"status_code": 403})()),
            "airtable_request_failed",
        ),
        (requests.ConnectionError("down"), "airtable_unavailable"),
    ],
)
async def test_errors_become_airtable_error(error: Exception, code: str) -> None:
    client, _ = make_client(FakeTable(error))
    with pytest.raises(AirtableError) as exc:
        await client.list_records("t")
    assert exc.value.code == code


async def test_list_fields() -> None:
    client, _ = make_client(FakeTable([]))
    fields = await client.list_fields("수강생 정보 시트")
    assert [(f.name, f.type) for f in fields] == [
        ("이름", "singleLineText"),
        ("기수", "multipleLookupValues"),
    ]

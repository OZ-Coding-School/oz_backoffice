from typing import Any

import pytest

from app.contexts.academy.infrastructure.airtable_source import AirtableRosterSource
from app.integrations.airtable.client import AirtableRecord

pytestmark = pytest.mark.unit


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, list[str] | None]] = []

    async def list_records(
        self, table: str, *, formula: str | None = None, fields: list[str] | None = None
    ) -> list[AirtableRecord]:
        self.calls.append((table, formula, fields))
        return [AirtableRecord(id="rec1", fields={"이름": "김오즈"})]


async def test_fetch_returns_id_and_fields() -> None:
    client = FakeClient()
    source = AirtableRosterSource(client, table="tblROSTER")  # type: ignore[arg-type]
    rows: list[tuple[str, dict[str, Any]]] = await source.fetch("{기수}='x'", ["이름"])
    assert rows == [("rec1", {"이름": "김오즈"})]
    assert client.calls == [("tblROSTER", "{기수}='x'", ["이름"])]

"""Airtable 수강생 명단 원천 (RosterSource 구현)."""

from typing import Any

from app.integrations.airtable.client import AirtableClient


class AirtableRosterSource:
    def __init__(self, client: AirtableClient, *, table: str) -> None:
        self._client = client
        self._table = table

    async def fetch(self, formula: str, fields: list[str]) -> list[tuple[str, dict[str, Any]]]:
        records = await self._client.list_records(self._table, formula=formula, fields=fields)
        return [(record.id, record.fields) for record in records]

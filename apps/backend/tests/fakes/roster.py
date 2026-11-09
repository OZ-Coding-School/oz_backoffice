"""가짜 Airtable 명단 원천. 동기화 서비스가 만드는 범위 수식을 해석해 레코드를 거른다.

지원하는 수식: None(전체), {필드}='<값>', ARRAYJOIN({기수})='<라벨>',
FIND('<별칭> ', ARRAYJOIN({기수}))=1, 그 OR.
"""

import re
from typing import Any

_EXACT = re.compile(r"^ARRAYJOIN\(\{(?P<field>[^}]+)\}\)='(?P<value>.*)'$")
_CODE = re.compile(r"^\{(?P<field>[^}]+)\}='(?P<value>.*)'$")
_PREFIX = re.compile(r"FIND\('(?P<prefix>[^']*)', ARRAYJOIN\(\{(?P<field>[^}]+)\}\)\)=1")


class FakeRosterSource:
    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records: dict[str, dict[str, Any]] = records or {}
        self.formulas: list[str | None] = []
        self.fail_with: Exception | None = None

    def put(self, record_id: str, **fields: Any) -> None:
        self.records[record_id] = fields

    async def fetch(
        self, formula: str | None, fields: list[str]
    ) -> list[tuple[str, dict[str, Any]]]:
        self.formulas.append(formula)
        if self.fail_with:
            raise self.fail_with
        return [
            (record_id, {k: v for k, v in values.items() if k in fields})
            for record_id, values in self.records.items()
            if self._matches(formula, values)
        ]

    @staticmethod
    def _label(values: dict[str, Any], field: str) -> str:
        value = values.get(field)
        return ", ".join(value) if isinstance(value, list) else str(value or "")

    def _matches(self, formula: str | None, values: dict[str, Any]) -> bool:
        if formula is None:
            return True
        code = _CODE.match(formula)
        if code:
            return str(values.get(code["field"])) == code["value"]
        exact = _EXACT.match(formula)
        if exact:
            return self._label(values, exact["field"]) == exact["value"]
        prefixes = _PREFIX.findall(formula)
        if not prefixes:
            raise ValueError(f"가짜 원천이 해석할 수 없는 수식: {formula}")
        return any(self._label(values, field).startswith(prefix) for prefix, field in prefixes)

"""Airtable 과정-기수 테이블 레코드 해석 (decisions A20). 순수 함수만 둔다.

레코드 1건 = 기수 1개. 운영과정은 과정코드로, HRD 과정은 훈련과정ID로, HRD 회차는
(HRD 과정, 훈련회차)로 찾는다. 기수의 HRD 회차는 운영과정의 대표 HRD 과정과 달라도 된다 (D6).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.domain.roster import (
    CohortLabel,
    UnmappedRecord,
    first,
    parse_cohort_label,
    quote_formula,
)

COHORT_STATUS_BY_TEXT: dict[str, CohortStatus] = {
    "개강 전": CohortStatus.PLANNED,
    "훈련 중": CohortStatus.ONGOING,
    "취업 산정 기간": CohortStatus.ENDED,
    "취업 산정 종료": CohortStatus.ENDED,
}

# 운영진이 정하는 상태. 동기화가 덮어쓰지 않는다
MANUAL_COHORT_STATUSES = frozenset({CohortStatus.INACTIVE, CohortStatus.ARCHIVED})


@dataclass(frozen=True, slots=True)
class CohortFieldMap:
    label: str = "캠프기수"
    code: str = "과정코드"
    hrd_net_id: str = "훈련과정ID"
    hrd_name: str = "훈련과정명"
    hrd_round: str = "훈련회차"
    start: str = "훈련시작일"
    end: str = "훈련종료일"
    status: str = "과정 진행상태"

    def fetch_fields(self) -> list[str]:
        return [
            self.label,
            self.code,
            self.hrd_net_id,
            self.hrd_name,
            self.hrd_round,
            self.start,
            self.end,
            self.status,
        ]


@dataclass(frozen=True, slots=True)
class CohortSource:
    record_id: str
    label: CohortLabel
    code: str
    hrd_net_id: str
    hrd_name: str
    hrd_round: int
    start_date: date
    end_date: date
    status: CohortStatus | None


def _text(value: Any) -> str | None:
    value = first(value)
    text = str(value).strip() if value is not None else ""
    return text or None


def _date(value: Any) -> date | None:
    text = _text(value)
    try:
        return date.fromisoformat(text[:10]) if text else None
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    text = _text(value)
    return int(text) if text and text.isdigit() else None


def interpret_cohort(
    record_id: str, fields: dict[str, Any], field_map: CohortFieldMap
) -> CohortSource | UnmappedRecord | None:
    """기수 라벨이 없으면 None(대상 아님). 필수 값이 없거나 틀리면 실패 목록 대상."""
    label = parse_cohort_label(fields.get(field_map.label))
    if label is None:
        return None
    code = (_text(fields.get(field_map.code)) or "").upper()
    hrd_net_id = _text(fields.get(field_map.hrd_net_id))
    hrd_name = _text(fields.get(field_map.hrd_name))
    hrd_round = _int(fields.get(field_map.hrd_round))
    start = _date(fields.get(field_map.start))
    end = _date(fields.get(field_map.end))
    if not (code.isalnum() and hrd_net_id and hrd_name and hrd_round and start and end):
        return UnmappedRecord(record_id, None, str(label), "invalid_cohort_record")
    return CohortSource(
        record_id=record_id,
        label=label,
        code=code,
        hrd_net_id=hrd_net_id,
        hrd_name=hrd_name,
        hrd_round=hrd_round,
        start_date=start,
        end_date=end,
        status=COHORT_STATUS_BY_TEXT.get(_text(fields.get(field_map.status)) or ""),
    )


def code_formula(field_name: str, code: str) -> str:
    """과정코드가 같은 기수 레코드 (과정·기수 범위 동기화)."""
    if "{" in field_name or "}" in field_name:
        raise ValueError(f"필드명에 중괄호를 쓸 수 없습니다: {field_name}")
    return f"{{{field_name}}}={quote_formula(code)}"

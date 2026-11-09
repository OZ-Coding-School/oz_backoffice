"""Airtable 수강생 명단 레코드 해석 (decisions A18·A19). 순수 함수만 둔다.

레코드 → 기수 라벨("헬스케어 3기") 분해, 이름·휴대폰·이메일 정규화, 상태 매핑.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.shared.errors import BusinessRuleViolation
from app.shared.normalization import normalize_name, normalize_phone

_COHORT_LABEL = re.compile(r"^(?P<prefix>.+?)\s*(?P<number>\d+)기$")

# Airtable `상태` → 수강 상태 (A19)
ENROLLMENT_BY_STATUS: dict[str, EnrollmentStatus] = {
    "수강중": EnrollmentStatus.ENROLLED,
    "정상수료": EnrollmentStatus.COMPLETED,
    "80%이상수료": EnrollmentStatus.COMPLETED,
    "조기수료": EnrollmentStatus.COMPLETED,
    "조기취업": EnrollmentStatus.EARLY_EMPLOYED,
    "80%수료후취업": EnrollmentStatus.EARLY_EMPLOYED,
    "70%이상조기취업": EnrollmentStatus.EARLY_EMPLOYED,
    "수강철회": EnrollmentStatus.DROPPED,
    "중도탈락": EnrollmentStatus.DROPPED,
    "하차": EnrollmentStatus.DROPPED,
    "제적": EnrollmentStatus.DROPPED,
    "개강전취소": EnrollmentStatus.DROPPED,
}

# Airtable `HRD상태` → HRD-Net 상태
HRD_STATUS_BY_TEXT: dict[str, StudentStatus] = {
    "모집중": StudentStatus.REGISTERED,
    "수강중": StudentStatus.TRAINING,
    "정상수료": StudentStatus.COMPLETED,
    "80%이상수료": StudentStatus.COMPLETED_80_PERCENT,
    "수료후취업": StudentStatus.COMPLETED_AND_EMPLOYED,
    "조기취업": StudentStatus.EARLY_EMPLOYED,
    "수강철회": StudentStatus.WITHDRAWAL,
    "중도탈락": StudentStatus.DROPPED_OUT,
    "하차": StudentStatus.LEAVE,
    "제적": StudentStatus.EXPELLED,
}


@dataclass(frozen=True, slots=True)
class RosterFieldMap:
    """Airtable 필드명 (설정으로 바꿀 수 있다)."""

    name: str = "이름"
    phone: str = "전화번호"
    email: str = "이메일"
    cohort: str = "기수"
    cohort_link: str = "취업운영시트 link"  # 과정-기수 테이블 레코드 링크 (A20)
    status: str = "상태"
    hrd_status: str = "HRD상태"
    dropped_on: str = "중도탈락일"
    training_end: str = "훈련종료일"

    def fetch_fields(self) -> list[str]:
        return [
            self.name,
            self.phone,
            self.email,
            self.cohort,
            self.cohort_link,
            self.status,
            self.hrd_status,
            self.dropped_on,
            self.training_end,
        ]


@dataclass(frozen=True, slots=True)
class CohortLabel:
    prefix: str
    number: int

    def __str__(self) -> str:
        return f"{self.prefix} {self.number}기"


@dataclass(frozen=True, slots=True)
class RosterRecord:
    """정규화한 명단 레코드 1건."""

    record_id: str
    cohort_record_id: str | None  # 과정-기수 테이블 레코드 링크 (있으면 이것으로 기수를 찾는다)
    cohort: CohortLabel | None  # 기수 라벨 (링크가 없을 때 대신 쓴다)
    name: str
    phone_number: str | None
    email: str | None
    status_text: str | None
    enrollment_status: EnrollmentStatus
    hrd_status: StudentStatus
    ended_on: date | None
    source_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UnmappedRecord:
    """동기화하지 못한 레코드 (운영진 확인 대상, roster_sync_runs.unmapped_records)."""

    record_id: str
    name: str | None
    cohort_label: str | None
    reason: str  # cohort_not_found | cohort_changed | invalid_name
    existing_student_id: uuid.UUID | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "airtable_record_id": self.record_id,
            "name": self.name,
            "cohort_label": self.cohort_label,
            "reason": self.reason,
            "existing_student_id": str(self.existing_student_id)
            if self.existing_student_id
            else None,
        }


def first(value: Any) -> Any:
    """lookup·수식 필드는 리스트로 온다. 첫 값을 꺼낸다."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_cohort_label(value: Any) -> CohortLabel | None:
    text = first(value)
    if not isinstance(text, str):
        return None
    match = _COHORT_LABEL.match(text.strip())
    if match is None:
        return None
    return CohortLabel(prefix=match["prefix"].strip(), number=int(match["number"]))


def _text(value: Any) -> str | None:
    value = first(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _phone(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return normalize_phone(text)
    except BusinessRuleViolation:
        return None  # 형식이 틀린 번호는 비워 둔다 (가입 매칭에서 빠짐)


def _email(value: Any) -> str | None:
    text = _text(value)
    return text.lower() if text and "@" in text else None


def _date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def enrollment_status_of(status_text: str | None, hrd_status: StudentStatus) -> EnrollmentStatus:
    """`상태`가 없거나 모르는 값이면 `HRD상태`로 보조 판단하고, 그것도 없으면 수강 중으로 본다."""
    if status_text in ENROLLMENT_BY_STATUS:
        return ENROLLMENT_BY_STATUS[status_text]
    by_hrd = {
        StudentStatus.COMPLETED: EnrollmentStatus.COMPLETED,
        StudentStatus.COMPLETED_80_PERCENT: EnrollmentStatus.COMPLETED,
        StudentStatus.COMPLETED_AND_EMPLOYED: EnrollmentStatus.EARLY_EMPLOYED,
        StudentStatus.EARLY_EMPLOYED: EnrollmentStatus.EARLY_EMPLOYED,
        StudentStatus.WITHDRAWAL: EnrollmentStatus.DROPPED,
        StudentStatus.DROPPED_OUT: EnrollmentStatus.DROPPED,
        StudentStatus.LEAVE: EnrollmentStatus.DROPPED,
        StudentStatus.EXPELLED: EnrollmentStatus.DROPPED,
    }
    return by_hrd.get(hrd_status, EnrollmentStatus.ENROLLED)


def interpret(
    record_id: str, fields: dict[str, Any], field_map: RosterFieldMap
) -> RosterRecord | UnmappedRecord | None:
    """레코드를 해석한다. 기수 링크도 기수 라벨도 없으면 None(동기화 대상 아님)."""
    cohort_record_id = _text(fields.get(field_map.cohort_link))
    cohort = parse_cohort_label(fields.get(field_map.cohort))
    if cohort_record_id is None and cohort is None:
        return None
    label = str(cohort) if cohort else cohort_record_id
    raw_name = _text(fields.get(field_map.name))
    try:
        name = normalize_name(raw_name or "")
    except BusinessRuleViolation:
        return UnmappedRecord(record_id, raw_name, label, "invalid_name")

    status_text = _text(fields.get(field_map.status))
    hrd_text = _text(fields.get(field_map.hrd_status))
    hrd_status = HRD_STATUS_BY_TEXT.get(hrd_text or "", StudentStatus.UNKNOWN)
    enrollment = enrollment_status_of(status_text, hrd_status)
    ended_on = None
    if enrollment is EnrollmentStatus.DROPPED:
        ended_on = _date(fields.get(field_map.dropped_on))
    elif enrollment is not EnrollmentStatus.ENROLLED:
        ended_on = _date(fields.get(field_map.training_end))
    return RosterRecord(
        record_id=record_id,
        cohort_record_id=cohort_record_id,
        cohort=cohort,
        name=name,
        phone_number=_phone(fields.get(field_map.phone)),
        email=_email(fields.get(field_map.email)),
        status_text=status_text,
        enrollment_status=enrollment,
        hrd_status=hrd_status,
        ended_on=ended_on,
        source_fields={k: fields[k] for k in field_map.fetch_fields() if k in fields},
    )


# ---------------------------------------------------------------- 범위 수식 (filterByFormula)
# `기수`가 lookup(리스트) 필드여도 동작하도록 ARRAYJOIN으로 문자열로 만든 뒤 비교한다
# (2026-11-09 실데이터로 검증, 구현 기록 19).
def quote_formula(value: str) -> str:
    """filterByFormula 문자열 리터럴 (역슬래시·작은따옴표 이스케이프)."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _cohort_text(field_name: str) -> str:
    if "{" in field_name or "}" in field_name:
        raise ValueError(f"필드명에 중괄호를 쓸 수 없습니다: {field_name}")
    return f"ARRAYJOIN({{{field_name}}})"


def cohort_formula(field_name: str, label: CohortLabel) -> str:
    return f"{_cohort_text(field_name)}={quote_formula(str(label))}"


def prefixes_formula(field_name: str, prefixes: list[str]) -> str:
    """기수 라벨이 주어진 과정 별칭 중 하나로 시작하는 레코드."""
    conditions = [f"FIND({quote_formula(p + ' ')}, {_cohort_text(field_name)})=1" for p in prefixes]
    return conditions[0] if len(conditions) == 1 else f"OR({', '.join(conditions)})"

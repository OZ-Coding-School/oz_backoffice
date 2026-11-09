"""교육 인력 계약과 계약서 (decisions M14, A23, A24, A25).

계약 상태 전이 (A24):
- DRAFT → ACTIVE: 운영진 확정. 계약서가 있어야 한다. 종료일이 이미 지났으면 바로 ENDED로 확정한다.
- ACTIVE → TERMINATED: 운영진 중도 해지.
- ACTIVE → ENDED: 종료일이 지난 다음 날 자동(매일 00:05 KST 작업). 종료일 당일까지는 ACTIVE다.
- ENDED·TERMINATED는 더 바뀌지 않는다.

수정·삭제 (A25): DRAFT일 때만 수정(계약서 교체 포함)·삭제한다. 확정 후에는 담당 직원만 바꿀 수 있다.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation
from app.shared.normalization import normalize_name, normalize_phone
from app.shared.value_objects import Email

TITLE_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 255

# DRAFT에서만 바꿀 수 있는 항목 (확정 후에는 manager_employee_id만 바꿀 수 있다)
DRAFT_FIELDS = frozenset(
    {
        "educator_type",
        "contractor_name",
        "contractor_email",
        "contractor_phone",
        "title",
        "start_date",
        "end_date",
        "manager_employee_id",
        "contract_file_id",
    }
)
CONFIRMED_FIELDS = frozenset({"manager_employee_id"})


@dataclass(kw_only=True, eq=False)
class ContractFile(Entity):
    """계약서 파일 (비공개 버킷 `contracts/` 객체). 교체·삭제해도 기록은 남긴다(deleted_at)."""

    file_name: str
    file_ext: str
    file_size: int
    storage_key: str
    created_at: datetime | None = None
    deleted_at: datetime | None = None

    def discard(self, *, now: datetime) -> None:
        if self.deleted_at is None:
            self.deleted_at = now


def _normalize_email(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    try:
        email = Email(raw).value
    except ValueError as exc:
        raise BusinessRuleViolation(
            "이메일 형식이 올바르지 않습니다.", code="invalid_email"
        ) from exc
    if len(email) > EMAIL_MAX_LENGTH:
        raise BusinessRuleViolation("이메일이 너무 깁니다.", code="invalid_email")
    return email


@dataclass(kw_only=True, eq=False)
class EducatorContract(AggregateRoot):
    manager_employee_id: uuid.UUID
    educator_type: EducatorType
    contractor_name: str
    contractor_phone: str
    title: str
    start_date: date
    end_date: date
    contractor_email: str | None = None
    contract_file_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None
    status: ContractStatus = ContractStatus.DRAFT
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.contractor_name = normalize_name(self.contractor_name)
        self.contractor_phone = normalize_phone(self.contractor_phone)
        self.contractor_email = _normalize_email(self.contractor_email)
        self.title = self.title.strip()
        if not self.title or len(self.title) > TITLE_MAX_LENGTH:
            raise BusinessRuleViolation(
                f"제목은 1~{TITLE_MAX_LENGTH}자여야 합니다.", code="invalid_contract_title"
            )
        if self.start_date > self.end_date:
            raise BusinessRuleViolation(
                "계약 시작일이 종료일보다 늦습니다.", code="invalid_contract_period"
            )

    @property
    def is_draft(self) -> bool:
        return self.status is ContractStatus.DRAFT

    def revised(self, changes: dict[str, object]) -> "EducatorContract":
        """바뀐 계약을 새로 만든다(생성과 같은 검증). 상태별로 바꿀 수 있는 항목만 허용한다."""
        allowed = DRAFT_FIELDS if self.is_draft else CONFIRMED_FIELDS
        if not set(changes) <= allowed:
            raise BusinessRuleViolation(
                "확정된 계약은 담당 직원 외에는 수정할 수 없습니다.",
                code="contract_not_editable",
            )
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]  # 허용 필드만 통과

    def confirm(self, *, today: date) -> None:
        if not self.is_draft:
            raise _invalid_transition()
        if self.contract_file_id is None:
            raise BusinessRuleViolation(
                "계약서를 올린 뒤 확정할 수 있습니다.", code="contract_file_required"
            )
        # 이미 끝난 계약을 뒤늦게 등록하면 바로 기간 만료로 확정한다
        self.status = ContractStatus.ENDED if self.end_date < today else ContractStatus.ACTIVE

    def terminate(self) -> None:
        if self.status is not ContractStatus.ACTIVE:
            raise _invalid_transition()
        self.status = ContractStatus.TERMINATED

    def expire(self, *, today: date) -> bool:
        """종료일이 지난 ACTIVE 계약을 ENDED로 바꾼다. 바뀌었으면 True."""
        if self.status is ContractStatus.ACTIVE and self.end_date < today:
            self.status = ContractStatus.ENDED
            return True
        return False

    def ensure_deletable(self) -> None:
        if not self.is_draft:
            raise BusinessRuleViolation(
                "작성 중(DRAFT)인 계약만 삭제할 수 있습니다.", code="contract_not_deletable"
            )


def _invalid_transition() -> BusinessRuleViolation:
    return BusinessRuleViolation(
        "현재 상태에서는 할 수 없는 작업입니다.", code="invalid_contract_transition"
    )

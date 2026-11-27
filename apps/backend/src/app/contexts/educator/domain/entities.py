"""계약과 계약서 (decisions A109, 이전 A23~A27).

상태 전이 (A109③):
- DRAFT → IN_PROGRESS: 계약 진행. 계약서가 있어야 한다.
- IN_PROGRESS → SIGNED·ACTIVE: 계약 완료. 시작일이 없거나 오늘 이전이면 바로 ACTIVE,
  아니면 SIGNED. 종료일이 이미 지났으면 바로 ENDED(뒤늦게 등록한 끝난 계약).
- SIGNED → ACTIVE: 시작일에 자동(매일 00:05 KST 작업).
- ACTIVE → ENDED: 종료일이 지난 다음 날 자동. 종료일이 없으면 운영진이 [종료].
- DRAFT·IN_PROGRESS → CANCELED (취소 사유·일자), SIGNED·ACTIVE → TERMINATED (해지 사유·상세·일자).

수정 (A109⑨): DRAFT·IN_PROGRESS는 모든 항목을 고치고, SIGNED·ACTIVE는 변경 계약(`amend`)으로만
내용·금액·기간·당사자 연락처를 바꾼다. 담당 직원은 상태와 무관하게 바꾼다. 삭제는 DRAFT만.
멘토·강사 연결 (A27·A104): 관리 정보라 상태와 무관하다. 멘토 계약은 항상 멘토에 속한다.
"""

import dataclasses
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.contexts.educator.domain.enums import (
    MENTOR_PRICE_UNITS,
    ContractStatus,
    ContractType,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    TerminationReason,
    VatType,
)
from app.shared.domain import AggregateRoot, Entity
from app.shared.errors import BusinessRuleViolation
from app.shared.normalization import normalize_name, normalize_phone
from app.shared.value_objects import Email

TITLE_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 255

NOTE_MAX_LENGTH = 500  # 금액 메모·취소 사유·해지 상세·변경 사유
CONTACT_PERSON_MAX_LENGTH = 50
_LANDLINE_RE = re.compile(r"^\d{9,11}$")
_BRN_RE = re.compile(r"^\d{10}$")

# 서명 전(DRAFT·IN_PROGRESS)에 고칠 수 있는 항목: 전부 (A109⑨)
DRAFT_FIELDS = frozenset(
    {
        "contract_type",
        "bootcamp_id",
        "cohort_id",
        "contractor_name",
        "contractor_email",
        "contractor_phone",
        "business_registration_number",
        "contact_person_name",
        "title",
        "start_date",
        "end_date",
        "settlement_type",
        "total_amount",
        "unit_price",
        "price_unit",
        "vat_type",
        "amount_note",
        "no_show_pay_amount",
        "mentoring_time_basis",
        "manager_employee_id",
        "contract_file_id",
    }
)
# 서명 후 변경 계약으로 바꿀 수 있는 항목 (A109⑨: 명칭·금액·기간·당사자 연락처)
AMENDABLE_FIELDS = frozenset(
    {
        "title",
        "start_date",
        "end_date",
        "settlement_type",
        "total_amount",
        "unit_price",
        "price_unit",
        "vat_type",
        "amount_note",
        "no_show_pay_amount",
        "mentoring_time_basis",
        "contractor_email",
        "contractor_phone",
        "business_registration_number",
        "contact_person_name",
    }
)
EDITABLE_STATUSES = frozenset({ContractStatus.DRAFT, ContractStatus.IN_PROGRESS})
AMENDABLE_STATUSES = frozenset({ContractStatus.SIGNED, ContractStatus.ACTIVE})
# 계약서가 없어도 되는 상태 (A109⑥: IN_PROGRESS부터 필수, 초안에서 바로 취소한 계약은 없음)
FILE_OPTIONAL_STATUSES = frozenset({ContractStatus.DRAFT, ContractStatus.CANCELED})


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


def _invalid(message: str, code: str) -> BusinessRuleViolation:
    return BusinessRuleViolation(message, code=code)


def _optional_text(raw: str | None, *, max_length: int, code: str) -> str | None:
    if raw is None or not raw.strip():
        return None
    text = raw.strip()
    if len(text) > max_length:
        raise _invalid(f"{max_length}자 이하로 적어 주세요.", code)
    return text


def _digits(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or None


@dataclass(kw_only=True, eq=False)
class EducatorContract(AggregateRoot):
    manager_employee_id: uuid.UUID
    contract_type: ContractType
    bootcamp_id: uuid.UUID
    contractor_name: str
    title: str
    settlement_type: SettlementType
    cohort_id: uuid.UUID | None = None
    contractor_phone: str | None = None
    contractor_email: str | None = None
    business_registration_number: str | None = None
    contact_person_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    total_amount: int | None = None
    unit_price: int | None = None
    price_unit: PriceUnit | None = None
    vat_type: VatType = VatType.NOT_APPLICABLE
    amount_note: str | None = None
    no_show_pay_amount: int | None = None
    mentoring_time_basis: MentoringTimeBasis | None = None
    contract_file_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None
    status: ContractStatus = ContractStatus.DRAFT
    cancel_reason: str | None = None
    canceled_on: date | None = None
    termination_reason: TerminationReason | None = None
    termination_detail: str | None = None
    terminated_on: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.contractor_name = normalize_name(self.contractor_name)
        self.contractor_email = _normalize_email(self.contractor_email)
        self.title = self.title.strip()
        if not self.title or len(self.title) > TITLE_MAX_LENGTH:
            raise _invalid(f"제목은 1~{TITLE_MAX_LENGTH}자여야 합니다.", "invalid_contract_title")
        self._check_party()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise _invalid("계약 시작일이 종료일보다 늦습니다.", "invalid_contract_period")
        self.amount_note = _optional_text(
            self.amount_note, max_length=NOTE_MAX_LENGTH, code="invalid_amount_note"
        )
        self._check_amount()

    def _check_party(self) -> None:
        """멘토·강사는 휴대폰 필수(가입 매칭), 그 밖은 일반 번호·업체 칸 선택 (A109⑤)."""
        if self.contract_type.is_educator:
            if self.contractor_phone is None:
                raise _invalid("휴대폰 번호를 적어 주세요.", "invalid_phone_number")
            self.contractor_phone = normalize_phone(self.contractor_phone)
            if self.business_registration_number or self.contact_person_name:
                raise _invalid(
                    "멘토·강사 계약에는 사업자 정보를 적지 않습니다.", "invalid_contract_party"
                )
            self.business_registration_number = None
            self.contact_person_name = None
            return
        phone = _digits(self.contractor_phone)
        if phone is not None and not _LANDLINE_RE.fullmatch(phone):
            raise _invalid("전화번호는 숫자 9~11자리여야 합니다.", "invalid_phone_number")
        self.contractor_phone = phone
        brn = _digits(self.business_registration_number)
        if brn is not None and not _BRN_RE.fullmatch(brn):
            raise _invalid(
                "사업자등록번호는 숫자 10자리여야 합니다.", "invalid_business_registration_number"
            )
        self.business_registration_number = brn
        self.contact_person_name = _optional_text(
            self.contact_person_name,
            max_length=CONTACT_PERSON_MAX_LENGTH,
            code="invalid_contact_person_name",
        )

    def _check_amount(self) -> None:
        """정산 유형별 필수 칸과 멘토 계약 조건 (A109④⑩, DB check_contract_amount 등과 같음)."""
        for value in (self.total_amount, self.unit_price, self.no_show_pay_amount):
            if value is not None and value < 0:
                raise _invalid("금액은 0 이상이어야 합니다.", "invalid_contract_amount")
        kind = self.settlement_type
        if kind is SettlementType.FIXED and self.total_amount is None:
            raise _invalid("정액 계약은 계약 금액(총액)이 필요합니다.", "invalid_contract_amount")
        if kind is SettlementType.UNIT_PRICE:
            if self.unit_price is None or self.price_unit is None:
                raise _invalid(
                    "단가 계약은 단가와 단가 기준이 필요합니다.", "invalid_contract_amount"
                )
        elif self.unit_price is not None or self.price_unit is not None:
            raise _invalid("단가는 단가 계약에만 적습니다.", "invalid_contract_amount")
        if self.contract_type is ContractType.MENTOR:
            if kind is not SettlementType.UNIT_PRICE or self.price_unit not in MENTOR_PRICE_UNITS:
                raise _invalid(
                    "멘토 계약은 시간 또는 회 단가여야 합니다.", "invalid_mentor_contract_terms"
                )
            if self.no_show_pay_amount is None or self.mentoring_time_basis is None:
                raise _invalid(
                    "멘토 계약은 노쇼 금액과 정산 시간 기준이 필요합니다.",
                    "invalid_mentor_contract_terms",
                )
        elif self.no_show_pay_amount is not None or self.mentoring_time_basis is not None:
            raise _invalid(
                "노쇼 금액·정산 시간 기준은 멘토 계약에만 적습니다.",
                "invalid_mentor_contract_terms",
            )

    @property
    def is_draft(self) -> bool:
        return self.status is ContractStatus.DRAFT

    @property
    def is_editable(self) -> bool:
        return self.status in EDITABLE_STATUSES

    def revised(self, changes: dict[str, Any]) -> "EducatorContract":
        """바뀐 계약을 새로 만든다(생성과 같은 검증). 서명 전에는 모든 항목, 뒤에는 담당 직원만."""
        allowed = DRAFT_FIELDS if self.is_editable else frozenset({"manager_employee_id"})
        if not set(changes) <= allowed:
            raise _invalid(
                "서명된 계약은 변경 계약으로 바꿔 주세요 (담당 직원은 바로 바꿀 수 있습니다).",
                "contract_not_editable",
            )
        updated = dataclasses.replace(self, **changes)
        updated.ensure_file_for_status()
        return updated

    def amended(self, changes: dict[str, Any]) -> "EducatorContract":
        """변경 계약 (A109⑨): SIGNED·ACTIVE에서 명칭·금액·기간·연락처만 바꾼 새 계약."""
        if self.status not in AMENDABLE_STATUSES:
            raise _invalid_transition()
        if not changes:
            raise _invalid("바꿀 항목이 없습니다.", "amendment_no_changes")
        if not set(changes) <= AMENDABLE_FIELDS:
            raise _invalid(
                "종류·과정·기수·당사자 이름은 변경 계약으로 바꿀 수 없습니다.",
                "contract_field_not_amendable",
            )
        return dataclasses.replace(self, **changes)

    def ensure_file_for_status(self) -> None:
        if self.status not in FILE_OPTIONAL_STATUSES and self.contract_file_id is None:
            raise _invalid("계약서를 올려 주세요.", "contract_file_required")

    def start_progress(self) -> None:
        if self.status is not ContractStatus.DRAFT:
            raise _invalid_transition()
        if self.contract_file_id is None:
            raise _invalid("계약서를 올린 뒤 진행할 수 있습니다.", "contract_file_required")
        self.status = ContractStatus.IN_PROGRESS

    def sign(self, *, today: date) -> None:
        """계약 완료: 시작일이 없거나 지났으면 ACTIVE, 아니면 SIGNED. 이미 끝났으면 ENDED."""
        if self.status is not ContractStatus.IN_PROGRESS:
            raise _invalid_transition()
        self.status = ContractStatus.SIGNED
        self.advance(today=today)

    def advance(self, *, today: date) -> bool:
        """날짜에 따라 SIGNED → ACTIVE → ENDED로 넘긴다(매일 작업, 멱등). 바뀌었으면 True."""
        before = self.status
        if self.status is ContractStatus.SIGNED and (
            self.start_date is None or self.start_date <= today
        ):
            self.status = ContractStatus.ACTIVE
        if (
            self.status is ContractStatus.ACTIVE
            and self.end_date is not None
            and self.end_date < today
        ):
            self.status = ContractStatus.ENDED
        return self.status is not before

    def end(self) -> None:
        """종료일이 없는 이행 중 계약을 운영진이 끝낸다 (A109③)."""
        if self.status is not ContractStatus.ACTIVE:
            raise _invalid_transition()
        if self.end_date is not None:
            raise _invalid(
                "종료일이 있는 계약은 종료일이 지나면 자동으로 끝납니다.", "contract_has_end_date"
            )
        self.status = ContractStatus.ENDED

    def cancel(self, *, reason: str, on: date) -> None:
        if self.status not in EDITABLE_STATUSES:
            raise _invalid_transition()
        text = _optional_text(reason, max_length=NOTE_MAX_LENGTH, code="invalid_cancel_reason")
        if text is None:
            raise _invalid("취소 사유를 적어 주세요.", "invalid_cancel_reason")
        self.status = ContractStatus.CANCELED
        self.cancel_reason = text
        self.canceled_on = on

    def terminate(self, *, reason: TerminationReason, detail: str | None, on: date) -> None:
        if self.status not in AMENDABLE_STATUSES:
            raise _invalid_transition()
        self.status = ContractStatus.TERMINATED
        self.termination_reason = reason
        self.termination_detail = _optional_text(
            detail, max_length=NOTE_MAX_LENGTH, code="invalid_termination_detail"
        )
        self.terminated_on = on

    def link(self, *, mentor_id: uuid.UUID | None, instructor_id: uuid.UUID | None) -> None:
        """멘토·강사 프로필을 연결·변경·해제한다(둘 다 None이면 해제). 상태와 무관하다(A27).

        계약 종류와 프로필 종류가 같아야 한다(DB check_contract_type_link와 같은 규칙).
        """
        wrong_kind = (mentor_id is not None and self.contract_type is not ContractType.MENTOR) or (
            instructor_id is not None and self.contract_type is not ContractType.INSTRUCTOR
        )
        if wrong_kind:
            raise _invalid("계약 종류와 연결할 프로필 종류가 다릅니다.", "contract_type_mismatch")
        # 멘토 계약은 항상 멘토에 속한다. 다른 멘토로 옮길 수만 있다 (A104)
        if self.contract_type is ContractType.MENTOR and mentor_id is None:
            raise _invalid(
                "멘토 계약은 연결을 해제할 수 없습니다. 다른 멘토로 옮겨 주세요.",
                "mentor_contract_unlink_forbidden",
            )
        self.mentor_id = mentor_id
        self.instructor_id = instructor_id

    def ensure_deletable(self) -> None:
        if not self.is_draft:
            raise _invalid(
                "초안(DRAFT)인 계약만 삭제할 수 있습니다. 진행 중이면 취소해 주세요.",
                "contract_not_deletable",
            )


@dataclass(kw_only=True, eq=False)
class ContractAmendment(Entity):
    """서명 후 변경 계약 이력 (A109⑨). 계약에는 최신 값을 반영하고 바뀐 항목의 전·후 값을 남긴다."""

    contract_id: uuid.UUID
    amended_on: date
    reason: str
    before: dict[str, Any]
    after: dict[str, Any]
    created_by_user_id: uuid.UUID
    contract_file_id: uuid.UUID | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        text = _optional_text(
            self.reason, max_length=NOTE_MAX_LENGTH, code="invalid_amendment_reason"
        )
        if text is None:
            raise _invalid("변경 사유를 적어 주세요.", "invalid_amendment_reason")
        self.reason = text


def _invalid_transition() -> BusinessRuleViolation:
    return BusinessRuleViolation(
        "현재 상태에서는 할 수 없는 작업입니다.", code="invalid_contract_transition"
    )

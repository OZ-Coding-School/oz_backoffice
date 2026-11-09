"""academy 도메인 엔티티: HRD-Net 과정·회차, 운영과정, 기수, 수강 등록, 수강생 명단, 명단 동기화."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.contexts.academy.domain.enums import (
    CohortStatus,
    DayNightSeType,
    EnrollmentStatus,
    HRDNetTrainType,
    RosterSyncScope,
    RosterSyncStatus,
    RosterSyncTrigger,
    StudentStatus,
    WeekendSeType,
)
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation
from app.shared.normalization import normalize_name, normalize_phone


def _require(condition: bool, message: str, code: str) -> None:
    if not condition:
        raise BusinessRuleViolation(message, code=code)


def _non_negative(value: int | None) -> bool:
    return value is None or value >= 0


@dataclass(kw_only=True, eq=False)
class HrdNetBootcamp(AggregateRoot):
    """HRD-Net에 등록된 과정. 운영과정(Bootcamp) N개가 하나의 HRD 과정을 참조한다 (decisions D6)."""

    name: str
    hrd_net_id: str | None = None
    train_type: HRDNetTrainType | None = None
    ncs1_se: str | None = None
    ncs2_se: str | None = None
    ncs3_se: str | None = None
    weekend_se: WeekendSeType = WeekendSeType.WEEKDAY
    day_night_se: DayNightSeType = DayNightSeType.DAY
    total_train_fee: int | None = None
    train_fee_per_hour: int | None = None
    total_train_hours: int | None = None
    total_train_days: int | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        _require(
            0 < len(self.name) <= 100, "HRD 과정명은 1~100자여야 합니다.", "invalid_hrd_bootcamp"
        )
        _require(
            all(
                _non_negative(v)
                for v in (
                    self.total_train_fee,
                    self.train_fee_per_hour,
                    self.total_train_hours,
                    self.total_train_days,
                )
            ),
            "훈련비·시수·일수는 음수일 수 없습니다.",
            "invalid_hrd_bootcamp",
        )


@dataclass(kw_only=True, eq=False)
class HrdNetBootcampCohort(AggregateRoot):
    """HRD-Net 운영회차. (HRD 과정, 회차 번호)는 유일하다."""

    hrd_net_bootcamp_id: uuid.UUID
    cohort_number: int
    train_start_date: date | None = None
    train_end_date: date | None = None
    self_pay_amount: int | None = None

    def __post_init__(self) -> None:
        _require(self.cohort_number > 0, "회차 번호는 1 이상이어야 합니다.", "invalid_hrd_cohort")
        _require(
            self.train_start_date is None
            or self.train_end_date is None
            or self.train_start_date <= self.train_end_date,
            "훈련 시작일이 종료일보다 늦습니다.",
            "invalid_hrd_cohort",
        )
        _require(
            _non_negative(self.self_pay_amount),
            "자비부담금은 음수일 수 없습니다.",
            "invalid_hrd_cohort",
        )


@dataclass(kw_only=True, eq=False)
class Bootcamp(AggregateRoot):
    """사내 운영과정. code는 대문자 영문·숫자(AH, AL, GM ...).

    airtable_cohort_prefix: Airtable 수강생 명단의 기수 값 앞부분(예: "헬스케어 3기"의 "헬스케어").
    비어 있으면 명단 동기화 대상이 아니다 (decisions A18).
    """

    hrd_net_bootcamp_id: uuid.UUID
    name: str
    code: str
    is_active: bool = True
    airtable_cohort_prefix: str | None = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.code = self.code.strip().upper()
        if self.airtable_cohort_prefix is not None:
            self.airtable_cohort_prefix = self.airtable_cohort_prefix.strip() or None
        _require(
            self.airtable_cohort_prefix is None or len(self.airtable_cohort_prefix) <= 50,
            "Airtable 기수 별칭은 50자 이하여야 합니다.",
            "invalid_bootcamp",
        )
        _require(0 < len(self.name) <= 50, "운영과정명은 1~50자여야 합니다.", "invalid_bootcamp")
        _require(
            0 < len(self.code) <= 20 and self.code.isalnum(),
            "과정 코드는 1~20자의 영문·숫자여야 합니다.",
            "invalid_bootcamp",
        )


@dataclass(kw_only=True, eq=False)
class Cohort(AggregateRoot):
    """기수. (운영과정, 기수 번호)는 유일하다.

    운영과정과 HRD 회차는 같은 HRD 과정을 가리켜야 한다.
    이 일치 여부는 두 애그리거트를 조회하는 서비스에서 검증한다.
    """

    hrd_net_cohort_id: uuid.UUID
    bootcamp_id: uuid.UUID
    cohort_number: int
    start_date: date
    end_date: date
    status: CohortStatus = CohortStatus.PLANNED
    discord_guild_id: str | None = None

    def __post_init__(self) -> None:
        _require(self.cohort_number > 0, "기수 번호는 1 이상이어야 합니다.", "invalid_cohort")
        _require(
            self.start_date <= self.end_date, "기수 시작일이 종료일보다 늦습니다.", "invalid_cohort"
        )

    def change_status(self, status: CohortStatus) -> None:
        self.status = status


@dataclass(kw_only=True, eq=False)
class Student(AggregateRoot):
    """수강 등록. Airtable 수강생 명단 레코드 1건 = 기수 등록 1건 (decisions A10).

    - 가입 전에는 `user_id`가 None이다.
      가입 시 이름 + 휴대폰으로 매칭되면 `claim()`으로 회원을 연결한다.
    - 필드 원천:
      - Airtable: name, phone_number, email, hrd_net_status, source_fields
        → `apply_source()`로만 갱신한다.
      - 백오피스: status, ended_at, end_reason → 동기화가 덮어쓰지 않는다.
    - Airtable 없이 운영진이 직접 등록한 수강생은 `airtable_record_id`가 None이다.
    - (회원, 기수)는 유일하다. 회원 1명이 여러 기수를 들을 수 있다 (재수강).
    """

    cohort_id: uuid.UUID
    name: str
    hrd_net_status: StudentStatus
    enrolled_at: date
    user_id: uuid.UUID | None = None
    airtable_record_id: str | None = None
    phone_number: str | None = None
    email: str | None = None
    source_fields: dict[str, Any] | None = None
    synced_at: datetime | None = None
    is_removed_in_source: bool = False
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    ended_at: date | None = None
    end_reason: str | None = None

    def __post_init__(self) -> None:
        self.name = normalize_name(self.name)
        if self.phone_number is not None:
            self.phone_number = normalize_phone(self.phone_number)
        if self.email is not None:
            self.email = self.email.strip().lower() or None
        _require(
            self.airtable_record_id is None or bool(self.airtable_record_id.strip()),
            "Airtable 레코드 ID가 비어 있습니다.",
            "invalid_student",
        )
        _require(
            self.ended_at is None or self.enrolled_at <= self.ended_at,
            "종료일이 등록일보다 빠릅니다.",
            "invalid_student",
        )

    @property
    def is_enrolled(self) -> bool:
        return self.status is EnrollmentStatus.ENROLLED

    @property
    def is_claimed(self) -> bool:
        """회원 계정과 연결됐는지 (가입한 수강생인지)."""
        return self.user_id is not None

    def claim(self, user_id: uuid.UUID) -> None:
        """가입한 회원을 이 수강 등록에 연결한다."""
        _require(not self.is_claimed, "이미 회원과 연결된 수강생입니다.", "student_already_claimed")
        self.user_id = user_id

    def apply_source(
        self,
        *,
        name: str,
        phone_number: str | None,
        email: str | None,
        hrd_net_status: StudentStatus,
        source_fields: dict[str, Any],
        synced_at: datetime,
    ) -> None:
        """Airtable 동기화 값을 반영한다. 백오피스가 관리하는 수강 상태는 바꾸지 않는다."""
        self.name = normalize_name(name)
        self.phone_number = normalize_phone(phone_number) if phone_number else None
        self.email = (email.strip().lower() or None) if email else None
        self.hrd_net_status = hrd_net_status
        self.source_fields = source_fields
        self.synced_at = synced_at
        self.is_removed_in_source = False

    def sync_enrollment(
        self, status: EnrollmentStatus, *, ended_on: date | None, reason: str | None
    ) -> None:
        """Airtable `상태`로 수강 상태를 맞춘다 (decisions A19).

        백오피스에서만 정하는 기수 이동(TRANSFERRED)은 덮어쓰지 않는다.
        종료일이 등록일보다 빠르면(원천 데이터 오류) 종료일은 비워 둔다.
        """
        if self.status is EnrollmentStatus.TRANSFERRED:
            return
        self.status = status
        if status is EnrollmentStatus.ENROLLED:
            self.ended_at, self.end_reason = None, None
            return
        self.ended_at = ended_on if ended_on is not None and ended_on >= self.enrolled_at else None
        self.end_reason = reason

    def mark_removed_in_source(self) -> None:
        """Airtable에서 사라진 레코드. 멘토링 데이터가 참조하므로 행은 지우지 않는다."""
        self.is_removed_in_source = True

    def end(self, status: EnrollmentStatus, *, on: date, reason: str | None = None) -> None:
        """수료·중도포기·조기취업·기수 이동으로 수강을 종료한다."""
        _require(self.is_enrolled, "수강 중인 등록만 종료할 수 있습니다.", "student_not_enrolled")
        _require(
            status is not EnrollmentStatus.ENROLLED,
            "종료 상태를 지정해야 합니다.",
            "invalid_student",
        )
        _require(on >= self.enrolled_at, "종료일이 등록일보다 빠릅니다.", "invalid_student")
        self.status = status
        self.ended_at = on
        self.end_reason = reason


@dataclass(kw_only=True, eq=False)
class RosterSyncRun(AggregateRoot):
    """Airtable 명단 동기화 실행 이력. 범위: 전체 / 과정 / 기수 (decisions A9)."""

    trigger: RosterSyncTrigger
    scope_type: RosterSyncScope
    started_at: datetime
    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None
    status: RosterSyncStatus = RosterSyncStatus.RUNNING
    finished_at: datetime | None = None
    fetched_count: int = 0
    upserted_count: int = 0
    removed_count: int = 0
    unmapped_count: int = 0
    # 기수를 매핑하지 못한 Airtable 레코드 (students로 만들 수 없어 실행 이력에 남긴다)
    unmapped_records: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None

    def __post_init__(self) -> None:
        expected = {
            RosterSyncScope.ALL: (False, False),
            RosterSyncScope.BOOTCAMP: (True, False),
            RosterSyncScope.COHORT: (True, True),
        }[self.scope_type]
        _require(
            (self.bootcamp_id is not None, self.cohort_id is not None) == expected,
            "동기화 범위와 대상 과정·기수가 맞지 않습니다.",
            "invalid_roster_sync_scope",
        )

    def succeed(
        self,
        *,
        now: datetime,
        fetched: int,
        upserted: int,
        removed: int,
        unmapped_records: list[dict[str, Any]],
    ) -> None:
        self._finish(now)
        self.status = RosterSyncStatus.SUCCEEDED
        self.fetched_count = fetched
        self.upserted_count = upserted
        self.removed_count = removed
        self.unmapped_records = unmapped_records
        self.unmapped_count = len(unmapped_records)

    def fail(self, *, now: datetime, error_message: str) -> None:
        self._finish(now)
        self.status = RosterSyncStatus.FAILED
        self.error_message = error_message[:2000]

    def _finish(self, now: datetime) -> None:
        _require(
            self.status is RosterSyncStatus.RUNNING,
            "실행 중인 동기화만 종료할 수 있습니다.",
            "roster_sync_not_running",
        )
        self.finished_at = now

from datetime import date

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import EnrollmentStatus, StudentStatus
from app.contexts.academy.domain.roster import (
    CohortLabel,
    RosterFieldMap,
    RosterRecord,
    UnmappedRecord,
    enrollment_status_of,
    interpret,
    parse_cohort_label,
)
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

FIELDS = RosterFieldMap()


def fields(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "이름": " 김오즈 ",
        "전화번호": "010-1234-5678",
        "이메일": "Kim@Gmail.com",
        "기수": ["헬스케어 3기"],
        "상태": "수강중",
        "HRD상태": "수강중",
    }
    values.update(overrides)
    return {k: v for k, v in values.items() if v is not None}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["헬스케어 3기"], CohortLabel("헬스케어", 3)),
        ("BD 12기", CohortLabel("BD", 12)),
        (["AI리더1기"], CohortLabel("AI리더", 1)),
        ([], None),
        (None, None),
        ("헬스케어", None),
    ],
)
def test_parse_cohort_label(value: object, expected: CohortLabel | None) -> None:
    assert parse_cohort_label(value) == expected


def test_interpret_normalizes_record() -> None:
    record = interpret("rec1", fields(), FIELDS)
    assert isinstance(record, RosterRecord)
    assert (record.name, record.phone_number, record.email) == (
        "김오즈",
        "01012345678",
        "kim@gmail.com",
    )
    assert (record.cohort, record.enrollment_status, record.hrd_status) == (
        CohortLabel("헬스케어", 3),
        EnrollmentStatus.ENROLLED,
        StudentStatus.TRAINING,
    )
    assert record.source_fields["기수"] == ["헬스케어 3기"]


def test_interpret_bad_values() -> None:
    assert interpret("rec1", fields(기수=None), FIELDS) is None
    unmapped = interpret("rec1", fields(이름=None), FIELDS)
    assert isinstance(unmapped, UnmappedRecord)
    assert unmapped.reason == "invalid_name"
    odd = interpret("rec1", fields(전화번호="02-123-4567", 이메일="없음"), FIELDS)
    assert isinstance(odd, RosterRecord)
    assert (odd.phone_number, odd.email) == (None, None)


@pytest.mark.parametrize(
    ("status", "hrd", "expected"),
    [
        ("하차", "중도탈락", EnrollmentStatus.DROPPED),
        ("정상수료", "수강중", EnrollmentStatus.COMPLETED),  # 상태가 더 최신
        ("80%수료후취업", None, EnrollmentStatus.EARLY_EMPLOYED),
        ("개강전취소", "확인필요", EnrollmentStatus.DROPPED),
        (None, "중도탈락", EnrollmentStatus.DROPPED),  # 상태가 없으면 HRD상태로
        (None, None, EnrollmentStatus.ENROLLED),
        ("이상한값", "확인필요", EnrollmentStatus.ENROLLED),
    ],
)
def test_status_mapping(status: str | None, hrd: str | None, expected: EnrollmentStatus) -> None:
    record = interpret("rec1", fields(상태=status, HRD상태=hrd), FIELDS)
    assert isinstance(record, RosterRecord)
    assert record.enrollment_status is expected


def test_unknown_hrd_status() -> None:
    record = interpret("rec1", fields(HRD상태="확인필요"), FIELDS)
    assert isinstance(record, RosterRecord)
    assert record.hrd_status is StudentStatus.UNKNOWN
    assert enrollment_status_of(None, StudentStatus.UNKNOWN) is EnrollmentStatus.ENROLLED


def test_ended_on_comes_from_dropped_or_training_end() -> None:
    dropped = interpret(
        "r", fields(상태="중도탈락", 중도탈락일="2026-12-01", 훈련종료일="2027-04-30"), FIELDS
    )
    completed = interpret(
        "r", fields(상태="정상수료", 중도탈락일="2026-12-01", 훈련종료일="2027-04-30"), FIELDS
    )
    assert isinstance(dropped, RosterRecord)
    assert isinstance(completed, RosterRecord)
    assert (dropped.ended_on, completed.ended_on) == (date(2026, 12, 1), date(2027, 4, 30))


def test_student_sync_enrollment() -> None:
    student = Student(
        cohort_id=new_id(),
        name="김오즈",
        hrd_net_status=StudentStatus.TRAINING,
        enrolled_at=date(2026, 11, 1),
    )
    student.sync_enrollment(EnrollmentStatus.DROPPED, ended_on=date(2026, 12, 1), reason="하차")
    assert (student.status, student.ended_at, student.end_reason) == (
        EnrollmentStatus.DROPPED,
        date(2026, 12, 1),
        "하차",
    )
    # 등록일보다 빠른 종료일은 비운다
    student.sync_enrollment(EnrollmentStatus.DROPPED, ended_on=date(2020, 1, 1), reason="하차")
    assert student.ended_at is None
    # 다시 수강중이면 종료 정보를 지운다
    student.sync_enrollment(EnrollmentStatus.ENROLLED, ended_on=None, reason=None)
    assert (student.status, student.ended_at, student.end_reason) == (
        EnrollmentStatus.ENROLLED,
        None,
        None,
    )
    # 기수 이동은 백오피스 상태라 덮어쓰지 않는다
    student.end(EnrollmentStatus.TRANSFERRED, on=date(2026, 12, 1))
    student.sync_enrollment(EnrollmentStatus.COMPLETED, ended_on=None, reason="정상수료")
    assert student.status is EnrollmentStatus.TRANSFERRED

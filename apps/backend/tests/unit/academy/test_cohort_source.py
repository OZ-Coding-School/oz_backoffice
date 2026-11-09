from datetime import date

import pytest

from app.contexts.academy.domain.cohort_source import (
    CohortFieldMap,
    CohortSource,
    code_formula,
    interpret_cohort,
)
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.domain.roster import CohortLabel, UnmappedRecord

pytestmark = pytest.mark.unit

FIELDS = CohortFieldMap()


def record(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "캠프기수": "헬스케어 3기",
        "과정코드": "ah",
        "훈련과정ID": "AIG20250000501719",
        "훈련과정명": "헬스케어 과정",
        "훈련회차": "3",
        "훈련시작일": "2026-11-01",
        "훈련종료일": "2027-04-30",
        "과정 진행상태": "훈련 중",
    }
    values.update(overrides)
    return {k: v for k, v in values.items() if v is not None}


def test_interpret_cohort_record() -> None:
    source = interpret_cohort("recC", record(), FIELDS)
    assert source == CohortSource(
        record_id="recC",
        label=CohortLabel("헬스케어", 3),
        code="AH",
        hrd_net_id="AIG20250000501719",
        hrd_name="헬스케어 과정",
        hrd_round=3,
        start_date=date(2026, 11, 1),
        end_date=date(2027, 4, 30),
        status=CohortStatus.ONGOING,
    )


@pytest.mark.parametrize(
    ("text", "status"),
    [
        ("개강 전", CohortStatus.PLANNED),
        ("취업 산정 기간", CohortStatus.ENDED),
        ("이상한 값", None),
    ],
)
def test_cohort_status_mapping(text: str, status: CohortStatus | None) -> None:
    source = interpret_cohort("recC", record(**{"과정 진행상태": text}), FIELDS)
    assert isinstance(source, CohortSource)
    assert source.status is status


def test_missing_label_is_skipped_and_missing_values_are_unmapped() -> None:
    assert interpret_cohort("recC", record(캠프기수=None), FIELDS) is None
    for field in ("과정코드", "훈련과정ID", "훈련회차", "훈련시작일"):
        unmapped = interpret_cohort("recC", record(**{field: None}), FIELDS)
        assert isinstance(unmapped, UnmappedRecord)
        assert unmapped.reason == "invalid_cohort_record"


def test_code_formula() -> None:
    assert code_formula("과정코드", "AH") == "{과정코드}='AH'"

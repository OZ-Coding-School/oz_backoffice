"""academy 테스트 데이터 빌더."""

from datetime import UTC, date, datetime
from itertools import count
from typing import Any

from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
    Student,
)
from app.contexts.academy.domain.enums import StudentStatus
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
)
from app.shared.ids import new_id

_seq = count(1)
SYNCED_AT = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def make_student(**overrides: Any) -> Student:
    """Airtable에서 동기화된(아직 가입하지 않은) 수강생. cohort_id는 overrides로 넘긴다."""
    n = next(_seq)
    values: dict[str, Any] = {
        "cohort_id": new_id(),
        "airtable_record_id": f"rec{n:014d}",
        "name": f"수강생{n}",
        "phone_number": f"010{n:08d}",
        "hrd_net_status": StudentStatus.TRAINING,
        "enrolled_at": date(2026, 11, 1),
        "source_fields": {},
        "synced_at": SYNCED_AT,
    }
    values.update(overrides)
    return Student(**values)


async def create_cohort(code: str | None = None, cohort_number: int = 1) -> Cohort:
    """HRD 과정 → HRD 회차 → 운영과정 → 기수를 차례로 저장하고 기수를 돌려준다."""
    n = next(_seq)
    hrd = HrdNetBootcamp(name=f"HRD 과정 {n}", hrd_net_id=f"AIG{n:010d}")
    await TortoiseHrdNetBootcampRepository().add(hrd)
    hrd_cohort = HrdNetBootcampCohort(hrd_net_bootcamp_id=hrd.id, cohort_number=cohort_number)
    await TortoiseHrdNetBootcampCohortRepository().add(hrd_cohort)
    bootcamp = Bootcamp(hrd_net_bootcamp_id=hrd.id, name=f"운영과정 {n}", code=code or f"BC{n}")
    await TortoiseBootcampRepository().add(bootcamp)
    cohort = Cohort(
        id=new_id(),
        hrd_net_cohort_id=hrd_cohort.id,
        bootcamp_id=bootcamp.id,
        cohort_number=cohort_number,
        start_date=date(2026, 11, 1),
        end_date=date(2027, 4, 30),
    )
    await TortoiseCohortRepository().add(cohort)
    return cohort

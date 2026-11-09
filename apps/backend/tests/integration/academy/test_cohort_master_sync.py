from datetime import date
from typing import Any

import pytest

from app.contexts.academy.application.cohort_master_sync import CohortMasterSync
from app.contexts.academy.domain.cohort_source import CohortFieldMap
from app.contexts.academy.domain.enums import CohortStatus
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
)
from app.core.uow import UnitOfWork

pytestmark = pytest.mark.integration

FRONT_HRD = "AIG20230000455720"
IH_HRD = "AIG20240000459179"


def master() -> CohortMasterSync:
    return CohortMasterSync(
        field_map=CohortFieldMap(),
        hrd_bootcamps=TortoiseHrdNetBootcampRepository(),
        hrd_cohorts=TortoiseHrdNetBootcampCohortRepository(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
    )


def row(label: str, code: str, hrd: str, round_: int, **extra: Any) -> dict[str, Any]:
    return {
        "캠프기수": label,
        "과정코드": code,
        "훈련과정ID": hrd,
        "훈련과정명": f"HRD {hrd[-3:]}",
        "훈련회차": str(round_),
        "훈련시작일": "2026-01-01",
        "훈련종료일": "2026-06-30",
        "과정 진행상태": "훈련 중",
        **extra,
    }


async def apply(records: dict[str, dict[str, Any]]) -> Any:
    async with UnitOfWork():
        return await master().apply(list(records.items()))


async def test_builds_master_data_with_cross_hrd_cohorts() -> None:
    """CEO 1기·IH 1기는 프론트엔드 HRD 과정의 회차, IH 2·3기는 다른 HRD 과정 (D6 보완)."""
    records = {
        "recFE9": row("프론트 9기", "FE", FRONT_HRD, 9),
        "recCEO1": row("CEO 1기", "CEO", FRONT_HRD, 9),
        "recIH1": row("1인창업 1기", "IH", FRONT_HRD, 16),
        "recIH2": row("1인창업 2기", "IH", IH_HRD, 1),
        "recIH3": row("1인창업 3기", "IH", IH_HRD, 2),
    }
    result = await apply(records)

    assert (result.created_bootcamps, result.created_cohorts, result.unmapped) == (3, 5, [])
    bootcamps = TortoiseBootcampRepository()
    hrds = TortoiseHrdNetBootcampRepository()
    ih = await bootcamps.get_by_code("IH")
    assert ih is not None
    assert (ih.name, ih.airtable_cohort_prefix) == ("1인창업", "1인창업")
    ih_hrd = await hrds.get_by_hrd_net_id(IH_HRD)
    front_hrd = await hrds.get_by_hrd_net_id(FRONT_HRD)
    assert ih_hrd is not None
    assert front_hrd is not None
    assert ih.hrd_net_bootcamp_id == ih_hrd.id  # 대표 HRD = 기수가 가장 많은 HRD 과정
    cohorts = TortoiseCohortRepository()
    hrd_cohorts = TortoiseHrdNetBootcampCohortRepository()
    ih1 = await cohorts.get_by_airtable_record_id("recIH1")
    assert ih1 is not None
    ih1_hrd_cohort = await hrd_cohorts.get(ih1.hrd_net_cohort_id)
    assert ih1_hrd_cohort is not None
    assert (ih1_hrd_cohort.hrd_net_bootcamp_id, ih1_hrd_cohort.cohort_number) == (front_hrd.id, 16)
    ceo1 = await cohorts.get_by_airtable_record_id("recCEO1")
    fe9 = await cohorts.get_by_airtable_record_id("recFE9")
    assert ceo1 is not None
    assert fe9 is not None
    assert ceo1.hrd_net_cohort_id == fe9.hrd_net_cohort_id  # 같은 HRD 회차(프론트 9회차)를 공유
    assert ceo1.status is CohortStatus.ONGOING

    again = await apply(records)
    assert (again.created_bootcamps, again.created_cohorts, again.updated_cohorts) == (0, 0, 0)


async def test_updates_dates_and_status_but_keeps_manual_status() -> None:
    await apply(
        {"recA": row("헬스케어 1기", "AH", "AIG1", 1), "recB": row("헬스케어 2기", "AH", "AIG1", 2)}
    )
    cohorts = TortoiseCohortRepository()
    archived = await cohorts.get_by_airtable_record_id("recB")
    assert archived is not None
    archived.change_status(CohortStatus.ARCHIVED)
    await cohorts.save(archived)

    result = await apply(
        {
            "recA": row(
                "헬스케어 1기",
                "AH",
                "AIG1",
                1,
                훈련종료일="2026-07-31",
                **{"과정 진행상태": "취업 산정 기간"},
            ),
            "recB": row("헬스케어 2기", "AH", "AIG1", 2, **{"과정 진행상태": "취업 산정 종료"}),
        }
    )

    assert result.updated_cohorts == 1
    first = await cohorts.get_by_airtable_record_id("recA")
    second = await cohorts.get_by_airtable_record_id("recB")
    assert first is not None
    assert second is not None
    assert (first.end_date, first.status) == (date(2026, 7, 31), CohortStatus.ENDED)
    assert second.status is CohortStatus.ARCHIVED


async def test_existing_bootcamp_and_cohort_are_linked_by_code_and_number() -> None:
    first = await apply({"recA": row("게임개발 1기", "GM", "AIG2", 1)})
    assert first.created_cohorts == 1
    # 같은 코드·번호의 기수가 이미 있으면 새 레코드 ID로 연결만 한다
    linked = await apply({"recNEW": row("게임개발 1기", "GM", "AIG2", 1)})
    assert (linked.created_cohorts, linked.updated_cohorts) == (0, 1)
    cohort = await TortoiseCohortRepository().get_by_airtable_record_id("recNEW")
    assert cohort is not None


async def test_invalid_records_are_unmapped() -> None:
    result = await apply(
        {
            "recBad": row("BX 1기", "BX", "AIG3", 1, 훈련시작일="2026-12-01"),  # 기간 역전
            "recMissing": row("BX 2기", "", "AIG3", 2),  # 과정코드 없음
            "recNoLabel": {**row("BX 3기", "BX", "AIG3", 3), "캠프기수": ""},  # 기수 없음 → 건너뜀
        }
    )
    assert sorted((u.record_id, u.reason) for u in result.unmapped) == [
        ("recBad", "invalid_hrd_cohort"),  # HRD 회차 기간 검증에서 먼저 걸린다
        ("recMissing", "invalid_cohort_record"),
    ]

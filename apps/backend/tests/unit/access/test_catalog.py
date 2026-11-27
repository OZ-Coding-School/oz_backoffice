"""권한 정의 (A86·A87): 엔터티 × 조회/관리, 관리는 조회 포함, 개발 직위 묶음."""

import pytest

from app.contexts.access.domain.catalog import (
    DEV_POSITION_PERMISSIONS,
    PERMISSION_DEFINITIONS,
    PERMISSIONS,
    PERMISSIONS_BY_CODE,
    validate_permissions,
)
from app.shared.errors import BusinessRuleViolation

pytestmark = pytest.mark.unit


def test_definitions_are_consistent() -> None:
    assert len(PERMISSIONS) == len(PERMISSION_DEFINITIONS) == 42
    for p in PERMISSION_DEFINITIONS:
        if p.requires is not None:
            assert PERMISSIONS_BY_CODE[p.requires].entity == p.entity
    bound = {p.code.rsplit(".", 1)[0] for p in PERMISSION_DEFINITIONS if p.cohort_bound}
    assert bound == {
        "academy.cohort",
        "academy.roster",
        "member.approval",
        "educator.contract",  # 계약은 과정·기수에 속한다 (A109⑦)
        "mentoring.settings",
        "mentoring.assignment",
        "mentoring.team",
        "mentoring.balance",
        "mentoring.request",
        "mentoring.record",
        "mentoring.chat",
        "mentoring.settlement",
    }


def test_dev_position_bundles() -> None:
    lead, manager = DEV_POSITION_PERMISSIONS["팀리드"], DEV_POSITION_PERMISSIONS["운영 매니저"]
    assistant = DEV_POSITION_PERMISSIONS["조교"]
    assert assistant < manager < lead
    assert lead - manager == {
        "staff.assignment.read",
        "staff.assignment.manage",
        "org.employee.read",
    }
    for bundle in DEV_POSITION_PERMISSIONS.values():
        assert validate_permissions(bundle) == bundle


@pytest.mark.parametrize(
    ("codes", "error"),
    [
        (["org.department.manage"], "permission_requires_read"),
        (["academy.roster.sync"], "permission_requires_read"),
        (["mentoring.request.cancel"], "permission_requires_read"),
        (["mentoring.settlement.close"], "permission_requires_read"),
        (["no.such"], "permission_not_found"),
    ],
)
def test_validation(codes: list[str], error: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        validate_permissions(codes)
    assert exc.value.code == error
    assert validate_permissions(["org.department.read", "org.department.manage"]) == {
        "org.department.read",
        "org.department.manage",
    }

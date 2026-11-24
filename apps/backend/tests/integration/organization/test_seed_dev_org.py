"""개발 조직 데이터 시드 CLI (A62)."""

import pytest

from app.cli import seed_dev_org
from app.contexts.access.domain.catalog import DEV_POSITION_PERMISSIONS
from app.contexts.organization.domain.enums import AssignmentScope, DataScope
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampTeamRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseTeamRepository,
)
from app.core.config import Settings
from app.shared.errors import AppError
from tests.factories.academy import create_cohort
from tests.factories.organization import create_position, create_team

pytestmark = pytest.mark.integration


async def test_seed_dev_org_is_idempotent(settings: Settings) -> None:
    linked = await create_cohort()
    other_team = await create_team(bootcamp_ids=(linked.bootcamp_id,))
    free = await create_cohort()
    await create_position("조교", priority=9)  # 이미 있는 직위는 정의대로 맞춘다

    lines = await seed_dev_org(settings)

    assert any("교육운영본부" in line for line in lines)
    department = await TortoiseDepartmentRepository().get_by_name("교육운영본부")
    assert department is not None
    team = await TortoiseTeamRepository().find_by_department_and_name(department.id, "교육 1팀")
    assert team is not None
    repo = TortoiseEmployeePositionRepository()
    positions = {
        p.name: (p.priority, p.assignment_scope, p.data_scope) for p in await repo.list_all()
    }
    assert positions == {
        "팀리드": (1, AssignmentScope.COURSE, DataScope.ALL),
        "운영 매니저": (2, AssignmentScope.COURSE, DataScope.ASSIGNED),
        "조교": (3, AssignmentScope.COHORT, DataScope.ASSIGNED),
        "러닝 코치": (4, AssignmentScope.COURSE, DataScope.ASSIGNED),
    }
    # 권한은 비어 있을 때만 기본 묶음을 넣는다 (A87)
    by_name = {p.name: p.id for p in await repo.list_all()}
    assert await repo.permissions_of(by_name["조교"]) == DEV_POSITION_PERMISSIONS["조교"]
    await repo.replace_permissions(by_name["조교"], frozenset({"mentoring.request.read"}))
    links = TortoiseBootcampTeamRepository()
    assert await links.list_bootcamp_ids(team.id) == {free.bootcamp_id}
    assert await links.list_bootcamp_ids(other_team.id) == {linked.bootcamp_id}  # 그대로

    assert await seed_dev_org(settings) == ["바꿀 것이 없습니다 (이미 반영됨)."]
    assert await repo.permissions_of(by_name["조교"]) == {"mentoring.request.read"}  # 덮지 않음


async def test_seed_dev_org_refuses_production(settings: Settings) -> None:
    with pytest.raises(AppError) as exc:
        await seed_dev_org(settings.model_copy(update={"environment": "production"}))
    assert exc.value.code == "seed_not_allowed"
    assert await TortoiseDepartmentRepository().list_all() == []

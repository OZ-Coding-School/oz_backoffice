import pytest

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.org_service import (
    DepartmentChanges,
    OrganizationAdminService,
)
from app.contexts.organization.domain.enums import EmploymentType
from app.contexts.organization.infrastructure.repositories import (
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRepository,
)
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.organization import create_employee, create_position
from tests.factories.staff_review import create_applicant

pytestmark = pytest.mark.integration


def service() -> OrganizationAdminService:
    return OrganizationAdminService(
        departments=TortoiseDepartmentRepository(),
        positions=TortoiseEmployeePositionRepository(),
        employees=TortoiseEmployeeRepository(),
        audit=AuditRecorder(TortoiseAuditLogRepository(), SystemClock()),
        uow=UnitOfWork(),
    )


@pytest.fixture
async def actor() -> User:
    return await create_applicant()


async def test_department_tree_rules(actor: User) -> None:
    svc = service()
    root = await svc.create_department(
        name="교육본부", description="교육", parent_id=None, rules=None, actor_id=actor.id
    )
    team = await svc.create_department(
        name="1팀", description="운영", parent_id=root.id, rules="규칙", actor_id=actor.id
    )
    leaf = await svc.create_department(
        name="파트", description="파트", parent_id=team.id, rules=None, actor_id=actor.id
    )

    with pytest.raises(ConflictError) as dup:
        await svc.create_department(
            name=" 1팀 ", description="중복", parent_id=root.id, rules=None, actor_id=actor.id
        )
    assert dup.value.code == "department_name_taken"
    # 상위가 다르면 같은 이름 허용
    await svc.create_department(
        name="1팀", description="다른 본부", parent_id=None, rules=None, actor_id=actor.id
    )
    # 여러 단계 순환 금지: 본부를 손자 부서 아래로 옮길 수 없다
    with pytest.raises(BusinessRuleViolation) as cycle:
        await svc.update_department(
            root.id, DepartmentChanges(parent_id=leaf.id), actor_id=actor.id
        )
    assert cycle.value.code == "department_cycle"
    with pytest.raises(NotFoundError):
        await svc.update_department(
            team.id, DepartmentChanges(parent_id=new_id()), actor_id=actor.id
        )

    moved = await svc.update_department(
        leaf.id, DepartmentChanges(parent_id=None, name="독립 파트"), actor_id=actor.id
    )
    assert (moved.parent_id, moved.name) == (None, "독립 파트")
    renamed = await svc.update_department(team.id, DepartmentChanges(rules=None), actor_id=actor.id)
    assert (renamed.name, renamed.rules) == ("1팀", None)

    with pytest.raises(ConflictError) as in_use:
        await svc.delete_department(root.id, actor_id=actor.id)  # 1팀이 하위
    assert in_use.value.code == "in_use"
    await svc.delete_department(moved.id, actor_id=actor.id)
    logs = await AuditLogModel.filter(target_id=moved.id).order_by("created_at")
    assert [log.action for log in logs] == [
        "organization.department.create",
        "organization.department.update",
        "organization.department.delete",
    ]


async def test_positions(actor: User) -> None:
    svc = service()
    position = await svc.create_position(name="매니저", priority=3, actor_id=actor.id)
    with pytest.raises(ConflictError):
        await svc.create_position(name="매니저", priority=1, actor_id=actor.id)
    updated = await svc.update_position(position.id, name=None, priority=1, actor_id=actor.id)
    assert (updated.name, updated.priority) == ("매니저", 1)
    other = await create_position("조교")
    with pytest.raises(ConflictError):
        await svc.update_position(position.id, name="조교", priority=None, actor_id=actor.id)
    assert [p.id for p in await svc.list_positions()] == [position.id, other.id]

    employee = await create_employee()
    with pytest.raises(ConflictError) as in_use:
        await svc.delete_position(employee.position_id, actor_id=actor.id)
    assert in_use.value.code == "in_use"
    await svc.delete_position(position.id, actor_id=actor.id)


async def test_employee_transfer(actor: User) -> None:
    svc = service()
    employee = await create_employee()
    department = await svc.create_department(
        name="2팀", description="운영", parent_id=None, rules=None, actor_id=actor.id
    )

    moved = await svc.update_employee(
        employee.id,
        department_id=department.id,
        position_id=None,
        employment_type=EmploymentType.CONTRACT,
        actor_id=actor.id,
    )

    assert (moved.department_id, moved.position_id, moved.employment_type) == (
        department.id,
        employee.position_id,
        EmploymentType.CONTRACT,
    )
    page, total = await svc.list_employees(department_id=department.id, limit=10, offset=0)
    assert (total, [e.id for e in page]) == (1, [employee.id])
    with pytest.raises(NotFoundError):
        await svc.update_employee(
            employee.id,
            department_id=new_id(),
            position_id=None,
            employment_type=None,
            actor_id=actor.id,
        )
    with pytest.raises(NotFoundError):
        await svc.get_employee(new_id())

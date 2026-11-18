import pytest

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.domain.entities import User
from app.contexts.organization.application.org_service import (
    DepartmentChanges,
    EmployeeChanges,
    OrganizationAdminService,
    PositionChanges,
    TeamChanges,
)
from app.contexts.organization.domain.enums import AssignmentScope, EmploymentType
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampTeamRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseEmployeeRegistrationRepository,
    TortoiseEmployeeRepository,
    TortoiseTeamRepository,
)
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.organization import create_employee, create_position, create_team
from tests.factories.staff_review import create_applicant, create_registration

pytestmark = pytest.mark.integration


def service() -> OrganizationAdminService:
    return OrganizationAdminService(
        departments=TortoiseDepartmentRepository(),
        teams=TortoiseTeamRepository(),
        bootcamp_teams=TortoiseBootcampTeamRepository(),
        bootcamps=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        positions=TortoiseEmployeePositionRepository(),
        employees=TortoiseEmployeeRepository(),
        audit=AuditRecorder(TortoiseAuditLogRepository(), SystemClock()),
        uow=UnitOfWork(),
    )


@pytest.fixture
async def actor() -> User:
    return await create_applicant()


async def test_department_rules(actor: User) -> None:
    svc = service()
    department = await svc.create_department(
        name="교육본부", description="교육", rules=None, actor_id=actor.id
    )
    other = await svc.create_department(
        name="경영지원", description="지원", rules="규칙", actor_id=actor.id
    )
    with pytest.raises(ConflictError) as dup:
        await svc.create_department(
            name=" 교육본부 ", description="중복", rules=None, actor_id=actor.id
        )
    assert dup.value.code == "department_name_taken"
    with pytest.raises(ConflictError):
        await svc.update_department(other.id, DepartmentChanges(name="교육본부"), actor_id=actor.id)

    renamed = await svc.update_department(
        other.id, DepartmentChanges(name="경영본부", rules=None), actor_id=actor.id
    )
    assert (renamed.name, renamed.rules) == ("경영본부", None)
    same = await svc.update_department(
        department.id, DepartmentChanges(description="교육 총괄"), actor_id=actor.id
    )
    assert (same.name, same.description) == ("교육본부", "교육 총괄")

    team = await svc.create_team(
        department_id=department.id, name="교육 1팀", description=None, actor_id=actor.id
    )
    with pytest.raises(ConflictError) as in_use:
        await svc.delete_department(department.id, actor_id=actor.id)  # 팀이 참조 중
    assert in_use.value.code == "in_use"
    await svc.delete_team(team.id, move_to_team_id=None, actor_id=actor.id)
    await svc.delete_department(department.id, actor_id=actor.id)
    logs = await AuditLogModel.filter(target_id=department.id).order_by("created_at")
    assert [log.action for log in logs] == [
        "organization.department.create",
        "organization.department.update",
        "organization.department.delete",
    ]


async def test_team_rules(actor: User) -> None:
    svc = service()
    first = await svc.create_department(
        name="본부", description="본부", rules=None, actor_id=actor.id
    )
    second = await svc.create_department(
        name="지원", description="지원", rules=None, actor_id=actor.id
    )
    team = await svc.create_team(
        department_id=first.id, name="교육 1팀", description=" 운영 ", actor_id=actor.id
    )
    assert team.description == "운영"
    with pytest.raises(ConflictError) as dup:
        await svc.create_team(
            department_id=first.id, name="교육 1팀", description=None, actor_id=actor.id
        )
    assert dup.value.code == "team_name_taken"
    with pytest.raises(NotFoundError) as missing:
        await svc.create_team(
            department_id=new_id(), name="팀", description=None, actor_id=actor.id
        )
    assert missing.value.code == "department_not_found"
    # 다른 부서로 옮기면 그 부서 안에서 이름이 겹치지 않아야 한다
    await svc.create_team(
        department_id=second.id, name="교육 1팀", description=None, actor_id=actor.id
    )
    with pytest.raises(ConflictError):
        await svc.update_team(team.id, TeamChanges(department_id=second.id), actor_id=actor.id)
    moved = await svc.update_team(
        team.id,
        TeamChanges(department_id=second.id, name="교육 2팀", description=None),
        actor_id=actor.id,
    )
    assert (moved.department_id, moved.name, moved.description) == (second.id, "교육 2팀", None)
    kept = await svc.update_team(team.id, TeamChanges(description="설명"), actor_id=actor.id)
    assert (kept.name, kept.description) == ("교육 2팀", "설명")


async def test_bootcamp_team(actor: User) -> None:
    svc = service()
    cohort = await create_cohort()
    first, second = await create_team(), await create_team()

    assert await svc.set_bootcamp_team(cohort.bootcamp_id, first.id, actor_id=actor.id) == first.id
    await svc.set_bootcamp_team(cohort.bootcamp_id, second.id, actor_id=actor.id)
    listed = {team.id: ids for team, ids in await svc.list_teams()}
    assert listed == {first.id: [], second.id: [cohort.bootcamp_id]}
    await svc.set_bootcamp_team(cohort.bootcamp_id, second.id, actor_id=actor.id)  # 그대로
    await svc.set_bootcamp_team(cohort.bootcamp_id, None, actor_id=actor.id)
    assert all(ids == [] for _, ids in await svc.list_teams())

    with pytest.raises(NotFoundError) as no_bootcamp:
        await svc.set_bootcamp_team(new_id(), first.id, actor_id=actor.id)
    assert no_bootcamp.value.code == "bootcamp_not_found"
    with pytest.raises(NotFoundError) as no_team:
        await svc.set_bootcamp_team(cohort.bootcamp_id, new_id(), actor_id=actor.id)
    assert no_team.value.code == "team_not_found"
    logs = await AuditLogModel.filter(target_id=cohort.bootcamp_id).order_by("created_at")
    assert [log.after for log in logs] == [
        {"team_id": str(first.id)},
        {"team_id": str(second.id)},
        {"team_id": None},
    ]


async def test_positions(actor: User) -> None:
    svc = service()
    position = await svc.create_position(
        name="매니저", priority=3, assignment_scope=AssignmentScope.COURSE, actor_id=actor.id
    )
    with pytest.raises(ConflictError):
        await svc.create_position(
            name="매니저", priority=1, assignment_scope=None, actor_id=actor.id
        )
    updated = await svc.update_position(position.id, PositionChanges(priority=1), actor_id=actor.id)
    assert (updated.name, updated.priority, updated.assignment_scope) == (
        "매니저",
        1,
        AssignmentScope.COURSE,
    )
    cleared = await svc.update_position(
        position.id, PositionChanges(assignment_scope=None), actor_id=actor.id
    )
    assert cleared.assignment_scope is None
    other = await create_position("조교")
    with pytest.raises(ConflictError):
        await svc.update_position(position.id, PositionChanges(name="조교"), actor_id=actor.id)
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
        name="2팀", description="운영", rules=None, actor_id=actor.id
    )
    team = await create_team(department.id)

    moved = await svc.update_employee(
        employee.id,
        EmployeeChanges(
            department_id=department.id,
            team_id=team.id,
            employment_type=EmploymentType.CONTRACT,
        ),
        actor_id=actor.id,
    )

    assert (moved.department_id, moved.team_id, moved.position_id, moved.employment_type) == (
        department.id,
        team.id,
        employee.position_id,
        EmploymentType.CONTRACT,
    )
    page, total = await svc.list_employees(department_id=department.id, limit=10, offset=0)
    assert (total, [e.id for e in page]) == (1, [employee.id])
    direct = await svc.update_employee(
        employee.id, EmployeeChanges(team_id=None), actor_id=actor.id
    )
    assert (direct.department_id, direct.team_id) == (department.id, None)
    for changes in (EmployeeChanges(department_id=new_id()), EmployeeChanges(team_id=new_id())):
        with pytest.raises(NotFoundError):
            await svc.update_employee(employee.id, changes, actor_id=actor.id)
    with pytest.raises(NotFoundError):
        await svc.get_employee(new_id())


async def test_delete_team_moves_references(actor: User) -> None:
    """참조가 있는 팀은 옮길 팀을 지정해야 지울 수 있다 (A62)."""
    svc = service()
    cohort = await create_cohort()
    employee = await create_employee()
    team = await create_team(employee.department_id, bootcamp_ids=(cohort.bootcamp_id,))
    target = await create_team()
    await svc.update_employee(employee.id, EmployeeChanges(team_id=team.id), actor_id=actor.id)
    registration = await create_registration(await create_applicant())
    registration.update(
        department_id=registration.department_id,
        team_id=team.id,
        position_id=registration.position_id,
        employment_type=registration.employment_type,
        assignments=[],
    )
    registration.reject(now=SystemClock().now(), reason="이력")  # 처리된 신청 이력도 옮긴다
    await TortoiseEmployeeRegistrationRepository().save(registration)

    with pytest.raises(ConflictError) as in_use:
        await svc.delete_team(team.id, move_to_team_id=None, actor_id=actor.id)
    assert in_use.value.code == "team_in_use"
    with pytest.raises(BusinessRuleViolation) as same:
        await svc.delete_team(team.id, move_to_team_id=team.id, actor_id=actor.id)
    assert same.value.code == "invalid_move_to_team"
    with pytest.raises(NotFoundError):
        await svc.delete_team(team.id, move_to_team_id=new_id(), actor_id=actor.id)

    await svc.delete_team(team.id, move_to_team_id=target.id, actor_id=actor.id)

    assert (await svc.get_employee(employee.id)).team_id == target.id
    moved = await TortoiseEmployeeRegistrationRepository().get(registration.id)
    assert moved is not None
    assert moved.team_id == target.id
    assert {t.id: ids for t, ids in await svc.list_teams()} == {target.id: [cohort.bootcamp_id]}
    log = await AuditLogModel.get(target_id=team.id, action="organization.team.delete")
    assert log.after == {"moved_to_team_id": str(target.id)}
    # 참조가 없으면 옮길 팀 없이 지운다
    empty = await create_team()
    await svc.delete_team(empty.id, move_to_team_id=None, actor_id=actor.id)

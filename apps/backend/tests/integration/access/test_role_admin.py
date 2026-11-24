from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.access.application.role_admin import RoleAdministration
from app.contexts.access.application.roles import RoleAssignmentService
from app.contexts.access.domain.catalog import COHORT_ASSISTANT, SUPER_ADMIN
from app.contexts.access.domain.enums import RoleScopeKind, RoleScopeType
from app.contexts.access.domain.roles import Role
from app.contexts.access.infrastructure.repositories import (
    TortoiseRoleRepository,
    TortoiseUserRoleRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.domain.entities import User
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import FixedClock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.factories.academy import create_cohort
from tests.factories.identity import make_user
from tests.factories.staff_review import create_applicant, seed_roles

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


def service(now: datetime = NOW) -> RoleAdministration:
    return RoleAdministration(
        user_roles=TortoiseUserRoleRepository(),
        roles=TortoiseRoleRepository(),
        users=UserQueries(TortoiseUserRepository()),
        scopes=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), FixedClock(now)),
        uow=UnitOfWork(),
        clock=FixedClock(now),
    )


async def approved_user() -> User:
    user = await create_applicant()
    user.approve(now=NOW)
    await TortoiseUserRepository().save(user)
    return user


@pytest.fixture
async def boss() -> User:
    await seed_roles()
    user = await approved_user()
    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        user.id, SUPER_ADMIN, RoleScopeType.GLOBAL
    )
    return user


async def test_grant_list_and_revoke_super_admin(boss: User) -> None:
    other = await approved_user()
    expires = NOW + timedelta(days=1)

    granted = await service().grant(other.id, SUPER_ADMIN, actor_id=boss.id, expires_at=expires)

    roles = await service().list_for_user(other.id)
    assert [(r.id, r.role_code, r.expires_at) for r in roles] == [
        (granted.id, SUPER_ADMIN, expires)
    ]
    with pytest.raises(ConflictError) as exc:
        await service().grant(other.id, SUPER_ADMIN, actor_id=boss.id)
    assert exc.value.code == "role_already_granted"

    await service().revoke(other.id, granted.id, actor_id=boss.id)
    assert await service().list_for_user(other.id) == []
    actions = [
        log.action for log in await AuditLogModel.filter(target_id=other.id).order_by("created_at")
    ]
    assert actions == ["access.role.grant", "access.role.revoke"]


async def test_last_super_admin_cannot_be_revoked(boss: User) -> None:
    (only,) = await service().list_for_user(boss.id)
    with pytest.raises(ConflictError) as exc:
        await service().revoke(boss.id, only.id, actor_id=boss.id)
    assert exc.value.code == "last_super_admin"

    # 다른 최고 관리자가 생기면 자기 역할도 회수할 수 있다
    await service().grant((await approved_user()).id, SUPER_ADMIN, actor_id=boss.id)
    await service().revoke(boss.id, only.id, actor_id=boss.id)


async def test_expired_admin_does_not_count_as_remaining(boss: User) -> None:
    temp = await approved_user()
    grant = await service().grant(
        temp.id, SUPER_ADMIN, actor_id=boss.id, expires_at=NOW + timedelta(seconds=1)
    )
    later = service(NOW + timedelta(hours=1))
    (boss_role,) = await later.list_for_user(boss.id)
    with pytest.raises(ConflictError):
        await later.revoke(boss.id, boss_role.id, actor_id=boss.id)
    # 만료된 부여는 회수할 수 있다
    await later.revoke(temp.id, grant.id, actor_id=boss.id)


async def test_assignment_managed_roles_are_rejected(boss: User) -> None:
    user = await approved_user()
    with pytest.raises(BusinessRuleViolation) as exc:
        await service().grant(user.id, COHORT_ASSISTANT, actor_id=boss.id)
    assert exc.value.code == "role_managed_by_assignment"

    await RoleAssignmentService(TortoiseUserRoleRepository()).grant(
        user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, new_id()
    )
    (staff_role,) = await service().list_for_user(user.id)
    with pytest.raises(BusinessRuleViolation):
        await service().revoke(user.id, staff_role.id, actor_id=boss.id)


async def test_grant_and_revoke_errors(boss: User) -> None:
    pending = await create_applicant()
    with pytest.raises(BusinessRuleViolation) as not_approved:
        await service().grant(pending.id, SUPER_ADMIN, actor_id=boss.id)
    assert not_approved.value.code == "user_not_approved"
    with pytest.raises(BusinessRuleViolation) as past:
        await service().grant(
            (await approved_user()).id, SUPER_ADMIN, actor_id=boss.id, expires_at=NOW
        )
    assert past.value.code == "invalid_expires_at"
    with pytest.raises(NotFoundError):
        await service().grant(new_id(), SUPER_ADMIN, actor_id=boss.id)
    with pytest.raises(BusinessRuleViolation) as unknown:
        await service().grant(boss.id, "OWNER", actor_id=boss.id)
    assert unknown.value.code == "role_not_found"
    # 다른 회원의 역할 부여 ID로는 회수할 수 없다
    (boss_role,) = await service().list_for_user(boss.id)
    with pytest.raises(NotFoundError) as wrong_user:
        await service().revoke(pending.id, boss_role.id, actor_id=boss.id)
    assert wrong_user.value.code == "user_role_not_found"


async def add_role(code: str, kind: RoleScopeKind) -> None:
    await TortoiseRoleRepository().add(
        Role.create(code=code, name=code, description=None, scope_kind=kind)
    )


async def test_custom_roles_are_granted_in_their_scope(boss: User) -> None:
    await add_role("AUDITOR", RoleScopeKind.SCOPED)
    await add_role("ORG_EDITOR", RoleScopeKind.GLOBAL)
    cohort = await create_cohort()
    user = await approved_user()

    first = await service().grant(
        user.id,
        "AUDITOR",
        actor_id=boss.id,
        scope_type=RoleScopeType.COHORT,
        scope_id=cohort.id,
    )
    second = await service().grant(
        user.id,
        "AUDITOR",
        actor_id=boss.id,
        scope_type=RoleScopeType.BOOTCAMP,
        scope_id=cohort.bootcamp_id,
    )
    await service().grant(user.id, "ORG_EDITOR", actor_id=boss.id)
    assert {r.id for r in await service().list_for_user(user.id)} >= {first.id, second.id}
    await service().revoke(user.id, first.id, actor_id=boss.id)

    async def code_of(**kw: object) -> str:
        with pytest.raises((BusinessRuleViolation, NotFoundError)) as exc:
            await service().grant(user.id, actor_id=boss.id, **kw)  # type: ignore[arg-type]
        return exc.value.code

    assert await code_of(role_code="AUDITOR") == "invalid_role_scope"  # 전체 범위로는 안 됨
    assert (
        await code_of(role_code="AUDITOR", scope_type=RoleScopeType.COHORT) == "invalid_role_scope"
    )
    assert (
        await code_of(role_code="ORG_EDITOR", scope_type=RoleScopeType.COHORT, scope_id=cohort.id)
        == "invalid_role_scope"
    )
    assert (
        await code_of(role_code="AUDITOR", scope_type=RoleScopeType.COHORT, scope_id=new_id())
        == "cohort_not_found"
    )
    assert (
        await code_of(role_code="AUDITOR", scope_type=RoleScopeType.BOOTCAMP, scope_id=new_id())
        == "bootcamp_not_found"
    )


async def test_only_staff_accounts_can_receive_roles(boss: User) -> None:
    student = make_user()  # 수강생 계정
    student.approve(now=NOW)
    await TortoiseUserRepository().add(student)
    with pytest.raises(BusinessRuleViolation) as exc:
        await service().grant(student.id, SUPER_ADMIN, actor_id=boss.id)
    assert exc.value.code == "staff_only"

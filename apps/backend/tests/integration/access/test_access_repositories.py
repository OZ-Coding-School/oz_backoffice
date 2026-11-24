from datetime import UTC, datetime, timedelta

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.access.domain.catalog import (
    COHORT_ASSISTANT,
    LEGACY_PERMISSIONS,
    PERMISSIONS,
    ROLES,
    SUPER_ADMIN,
)
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.models import PermissionModel, RoleModel
from app.contexts.access.infrastructure.repositories import (
    TortoiseRoleCatalogRepository,
    TortoiseUserRoleRepository,
)
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.shared.errors import ConflictError
from app.shared.ids import new_id
from tests.factories.identity import make_user

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 6, tzinfo=UTC)


async def _permission_codes(role_code: str) -> set[str]:
    role = await RoleModel.get(code=role_code)
    return {p.code for p in await role.permissions.all()}


async def test_catalog_sync_is_idempotent_and_keeps_edited_mappings() -> None:
    catalog = TortoiseRoleCatalogRepository()
    await catalog.sync(ROLES, PERMISSIONS)
    await catalog.sync(ROLES, PERMISSIONS)

    assert await RoleModel.all().count() == len(ROLES)
    assert await _permission_codes(SUPER_ADMIN) == set(PERMISSIONS)
    assert "educator.contract.read" not in await _permission_codes(COHORT_ASSISTANT)

    # 화면에서 고친 매핑·이름은 다시 시드해도 덮지 않는다 (A84)
    assistant = await RoleModel.get(code=COHORT_ASSISTANT)
    await assistant.permissions.add(await PermissionModel.get(code="educator.contract.read"))
    assistant.name = "보조 매니저"
    await assistant.save()
    await catalog.sync(ROLES, PERMISSIONS)
    assert "educator.contract.read" in await _permission_codes(COHORT_ASSISTANT)
    assert (await RoleModel.get(code=COHORT_ASSISTANT)).name == "보조 매니저"

    # 최고 관리자에게는 빠진 권한을 다시 채운다
    admin = await RoleModel.get(code=SUPER_ADMIN)
    await admin.permissions.remove(await PermissionModel.get(code="org.department.read"))
    await catalog.sync(ROLES, PERMISSIONS)
    assert await _permission_codes(SUPER_ADMIN) == set(PERMISSIONS)


async def test_sync_converts_legacy_permission_codes_once() -> None:
    """예전 기능 묶음 코드를 가진 역할은 새 엔터티 코드로 바뀐다 (A86)."""
    catalog = TortoiseRoleCatalogRepository()
    await catalog.sync(ROLES, PERMISSIONS, LEGACY_PERMISSIONS)
    # 예전 상태 흉내: 조교에 contract.manage(예전 코드)와 mentoring.request.read만
    assistant = await RoleModel.get(code=COHORT_ASSISTANT)
    await assistant.permissions.clear()
    legacy = await PermissionModel.create(code="contract.manage", description="예전")
    await assistant.permissions.add(
        legacy, await PermissionModel.get(code="mentoring.request.read")
    )

    await catalog.sync(ROLES, PERMISSIONS, LEGACY_PERMISSIONS)
    assert await _permission_codes(COHORT_ASSISTANT) == {
        "educator.contract.read",
        "educator.contract.manage",
        "mentoring.request.read",
        "mentoring.record.read",
        "mentoring.chat.read",
    }
    assert not await PermissionModel.filter(code="contract.manage").exists()

    # 전환 뒤에는 화면에서 끈 권한을 다시 켜지 않는다
    assistant = await RoleModel.get(code=COHORT_ASSISTANT)
    await assistant.permissions.remove(await PermissionModel.get(code="mentoring.chat.read"))
    await catalog.sync(ROLES, PERMISSIONS, LEGACY_PERMISSIONS)
    assert "mentoring.chat.read" not in await _permission_codes(COHORT_ASSISTANT)


async def test_user_role_grant_lookup_and_expiry() -> None:
    await TortoiseRoleCatalogRepository().sync(ROLES, PERMISSIONS)
    user = make_user()
    await TortoiseUserRepository().add(user)
    repo = TortoiseUserRoleRepository()
    cohort_id = new_id()

    await repo.add(
        UserRole(user_id=user.id, role_code=SUPER_ADMIN, scope_type=RoleScopeType.GLOBAL)
    )
    await repo.add(
        UserRole(
            user_id=user.id,
            role_code=COHORT_ASSISTANT,
            scope_type=RoleScopeType.COHORT,
            scope_id=cohort_id,
            expires_at=NOW + timedelta(days=1),
        )
    )

    assert await repo.exists(user.id, SUPER_ADMIN, RoleScopeType.GLOBAL, None)
    assert await repo.exists(user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, cohort_id)
    assert not await repo.exists(user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, new_id())

    grants = await repo.list_grants(user.id, now=NOW)
    assert [(g.role_code, g.scope_id) for g in grants] == [
        (SUPER_ADMIN, None),
        (COHORT_ASSISTANT, cohort_id),
    ]
    later = await repo.list_grants(user.id, now=NOW + timedelta(days=2))
    assert [g.role_code for g in later] == [SUPER_ADMIN]


async def test_duplicate_global_role_is_rejected() -> None:
    await TortoiseRoleCatalogRepository().sync(ROLES, PERMISSIONS)
    user = make_user()
    await TortoiseUserRepository().add(user)
    repo = TortoiseUserRoleRepository()
    grant = {"user_id": user.id, "role_code": SUPER_ADMIN, "scope_type": RoleScopeType.GLOBAL}
    await repo.add(UserRole(**grant))  # type: ignore[arg-type]
    with pytest.raises(IntegrityError, match="uid_user_roles_user_role_scope"):
        await repo.add(UserRole(**grant))  # type: ignore[arg-type]


async def test_grant_requires_seeded_catalog() -> None:
    user = make_user()
    await TortoiseUserRepository().add(user)
    with pytest.raises(ConflictError) as exc:
        await TortoiseUserRoleRepository().add(
            UserRole(user_id=user.id, role_code=SUPER_ADMIN, scope_type=RoleScopeType.GLOBAL)
        )
    assert exc.value.code == "role_not_seeded"


@pytest.mark.parametrize(
    ("sql", "constraint"),
    [
        (
            "INSERT INTO user_roles (id, role_id, user_id, scope_type) "
            "SELECT gen_random_uuid(), r.id, u.id, 'COHORT' FROM roles r, users u LIMIT 1",
            "check_user_role_scope",
        ),
        (
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT role_id, permission_id FROM role_permissions LIMIT 1",
            "pk_role_permissions",
        ),
    ],
)
async def test_db_constraints(sql: str, constraint: str) -> None:
    await TortoiseRoleCatalogRepository().sync(ROLES, PERMISSIONS)
    await TortoiseUserRepository().add(make_user())
    with pytest.raises(IntegrityError, match=constraint):
        await connections.get("default").execute_query(sql)


async def test_remove_user_role_by_scope() -> None:
    await TortoiseRoleCatalogRepository().sync(ROLES, PERMISSIONS)
    user = make_user()
    await TortoiseUserRepository().add(user)
    repo = TortoiseUserRoleRepository()
    keep, drop = new_id(), new_id()
    for cohort_id in (keep, drop):
        await repo.add(
            UserRole(
                user_id=user.id,
                role_code=COHORT_ASSISTANT,
                scope_type=RoleScopeType.COHORT,
                scope_id=cohort_id,
            )
        )

    assert await repo.remove(user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, drop)
    assert not await repo.remove(user.id, COHORT_ASSISTANT, RoleScopeType.COHORT, drop)
    assert not await repo.remove(user.id, "UNKNOWN", RoleScopeType.GLOBAL, None)
    grants = await repo.list_grants(user.id, now=NOW)
    assert [g.scope_id for g in grants] == [keep]

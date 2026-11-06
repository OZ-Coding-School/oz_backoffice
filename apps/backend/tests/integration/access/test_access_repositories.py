from datetime import UTC, datetime, timedelta

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.access.domain.catalog import (
    COHORT_ASSISTANT,
    PERMISSIONS,
    ROLES,
    SUPER_ADMIN,
    RoleDefinition,
)
from app.contexts.access.domain.entities import UserRole
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.access.infrastructure.models import RoleModel
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


async def test_catalog_sync_is_idempotent_and_prunes_mappings() -> None:
    catalog = TortoiseRoleCatalogRepository()
    await catalog.sync(ROLES, PERMISSIONS)
    await catalog.sync(ROLES, PERMISSIONS)

    assert await RoleModel.all().count() == len(ROLES)
    assert await _permission_codes(SUPER_ADMIN) == set(PERMISSIONS)
    assert "contract.manage" not in await _permission_codes(COHORT_ASSISTANT)

    narrowed = [
        RoleDefinition(r.code, r.name, r.description, frozenset({"org.manage"}), r.scopes)
        if r.code == SUPER_ADMIN
        else r
        for r in ROLES
    ]
    await catalog.sync(narrowed, PERMISSIONS)
    assert await _permission_codes(SUPER_ADMIN) == {"org.manage"}


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

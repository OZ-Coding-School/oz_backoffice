import pytest

from app.cli import create_super_admin, main, seed_roles
from app.contexts.access.domain.catalog import ROLES, SUPER_ADMIN
from app.contexts.access.infrastructure.models import RoleModel
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("db")]


async def test_create_super_admin_on_real_db(settings: Settings) -> None:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings, name="대표")

    assert result.user_created
    assert result.role_granted
    user = await TortoiseUserRepository().get_by_email("boss@nextrunners.co.kr")
    assert user is not None
    assert (user.name, user.is_approved, user.is_active) == ("대표", True, True)
    assert await TortoiseUserRoleRepository().exists(user.id, SUPER_ADMIN, "GLOBAL", None)
    assert await AuditLogModel.filter(target_id=user.id, action="access.role.grant").count() == 1

    again = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    assert not again.user_created
    assert not again.role_granted


async def test_seed_roles_is_idempotent() -> None:
    await seed_roles()
    await seed_roles()
    assert await RoleModel.all().count() == len(ROLES)


def test_cli_rejects_missing_email(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["create-super-admin"])
    assert "email" in capsys.readouterr().err

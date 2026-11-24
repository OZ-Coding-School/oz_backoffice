import pytest

from app.cli import create_super_admin, main
from app.contexts.audit.infrastructure.models import AuditLogModel
from app.contexts.identity.domain.enums import AccountType
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.config import Settings

pytestmark = pytest.mark.integration


async def test_create_super_admin_on_real_db(settings: Settings) -> None:
    result = await create_super_admin("boss@nextrunners.co.kr", settings=settings, name="대표")

    assert result.user_created
    assert result.role_granted
    user = await TortoiseUserRepository().get_by_email("boss@nextrunners.co.kr")
    assert user is not None
    assert (user.name, user.is_approved, user.is_active) == ("대표", True, True)
    assert user.account_type is AccountType.STAFF
    assert user.is_super_admin
    assert (
        await AuditLogModel.filter(target_id=user.id, action="access.super_admin.enable").count()
        == 1
    )

    again = await create_super_admin("boss@nextrunners.co.kr", settings=settings)
    assert not again.user_created
    assert not again.role_granted


def test_cli_rejects_missing_email(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["create-super-admin"])
    assert "email" in capsys.readouterr().err

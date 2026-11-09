"""운영 CLI. 컨테이너 안에서 실행한다.

    docker compose exec api python -m app.cli create-super-admin admin@nextrunners.co.kr
    docker compose exec api python -m app.cli create-super-admin kim@nextrunners.co.kr --name 김오즈
    docker compose exec api python -m app.cli seed-roles
    docker compose exec api python -m app.cli send-test-mail someone@gmail.com

composition root라 각 컨텍스트의 infrastructure를 직접 조립한다.
"""

import argparse
import asyncio
import sys
import warnings
from collections.abc import Sequence

from tortoise import Tortoise

from app.contexts.access.application.bootstrap import SuperAdminBootstrap, SuperAdminResult
from app.contexts.access.application.roles import RoleAssignmentService, RoleCatalogSeeder
from app.contexts.access.infrastructure.repositories import (
    TortoiseRoleCatalogRepository,
    TortoiseUserRoleRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.database import build_tortoise_config
from app.core.logging import configure_logging
from app.core.notifications import build_mail_sender
from app.core.uow import UnitOfWork
from app.integrations.notifications.mail import MailMessage
from app.shared.errors import AppError


async def seed_roles() -> None:
    async with UnitOfWork():
        await RoleCatalogSeeder(TortoiseRoleCatalogRepository()).seed()


async def create_super_admin(
    email: str, *, settings: Settings, name: str | None = None
) -> SuperAdminResult:
    clock = SystemClock()
    bootstrap = SuperAdminBootstrap(
        seeder=RoleCatalogSeeder(TortoiseRoleCatalogRepository()),
        users=UserAdministration(TortoiseUserRepository(), clock),
        roles=RoleAssignmentService(TortoiseUserRoleRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        staff_domain=settings.google_allowed_domain,
    )
    return await bootstrap.run(email, name=name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="OZ 백오피스 운영 CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-super-admin", help="이메일로 최고 관리자를 등록한다")
    admin.add_argument("email", help="운영진 Google 계정 이메일")
    admin.add_argument("--name", help="회원이 없을 때 만들 이름 (기본: 이메일 앞부분)")
    commands.add_parser("seed-roles", help="역할·권한 정의를 DB에 맞춘다 (멱등)")
    mail = commands.add_parser("send-test-mail", help="현재 MAIL_DRIVER로 테스트 메일을 보낸다")
    mail.add_argument("to", help="받는 주소")
    return parser


async def send_test_mail(to: str, *, settings: Settings) -> str:
    sender = build_mail_sender(settings)
    await sender.send(
        MailMessage(
            to=to,
            subject=f"[{settings.mail_sender_name}] 메일 발송 설정 확인",
            text="백오피스 메일 발송 설정이 정상입니다.\n"
            "이 메일은 확인용이며 회신하지 않아도 됩니다.",
            html="<p>백오피스 메일 발송 설정이 정상입니다.</p>"
            "<p>이 메일은 확인용이며 회신하지 않아도 됩니다.</p>",
        )
    )
    return f"테스트 메일을 보냈습니다 (드라이버: {settings.mail_driver})."


async def _run(args: argparse.Namespace, settings: Settings) -> str:
    if args.command == "send-test-mail":  # DB가 필요 없다
        return await send_test_mail(args.to, settings=settings)
    await Tortoise.init(config=build_tortoise_config(settings.database_url, with_aerich=False))
    try:
        if args.command == "seed-roles":
            await seed_roles()
            return "역할·권한 정의를 반영했습니다."
        result = await create_super_admin(args.email, settings=settings, name=args.name)
        lines = [
            f"최고 관리자: {result.user.email} ({result.user.name})",
            "회원: 새로 만들었습니다. 이 이메일로 Google 로그인하면 연결됩니다."
            if result.user_created
            else "회원: 기존 회원입니다 (승인 상태).",
            "역할: SUPER_ADMIN을 부여했습니다."
            if result.role_granted
            else "역할: 이미 SUPER_ADMIN입니다.",
        ]
        return "\n".join(lines)
    finally:
        await Tortoise.close_connections()


def main(argv: Sequence[str] | None = None) -> int:
    # 아직 모델이 없는 컨텍스트 모듈(educator, mentoring)에 대한 Tortoise 경고는 CLI 출력에서 숨긴다
    warnings.filterwarnings("ignore", message=r"Module .* has no models")
    args = _parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)  # console 메일 드라이버 출력 등을 보이게 한다
    try:
        print(asyncio.run(_run(args, settings)))
    except AppError as exc:
        print(f"실패: {exc.message} ({exc.code})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

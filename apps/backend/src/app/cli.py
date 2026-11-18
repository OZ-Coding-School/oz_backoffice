"""운영 CLI. 컨테이너 안에서 실행한다.

    docker compose exec api python -m app.cli create-super-admin admin@nextrunners.co.kr
    docker compose exec api python -m app.cli create-super-admin kim@nextrunners.co.kr --name 김오즈
    docker compose exec api python -m app.cli seed-roles
    docker compose exec api python -m app.cli seed-dev-org
    docker compose exec api python -m app.cli send-test-mail someone@gmail.com
    docker compose exec -T api python -m app.cli export-openapi > apps/frontend/openapi.json

composition root라 각 컨텍스트의 infrastructure를 직접 조립한다.
"""

import argparse
import asyncio
import json
import sys
import warnings
from collections.abc import Sequence

from tortoise import Tortoise

from app.contexts.academy.infrastructure.repositories import TortoiseBootcampRepository
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
from app.contexts.organization.domain.entities import Department, EmployeePosition, Team
from app.contexts.organization.domain.enums import AssignmentScope
from app.contexts.organization.infrastructure.repositories import (
    TortoiseBootcampTeamRepository,
    TortoiseDepartmentRepository,
    TortoiseEmployeePositionRepository,
    TortoiseTeamRepository,
)
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


# 개발용 조직 데이터 (A62). 마이그레이션에서는 데이터를 넣지 않고 이 명령으로만 넣는다.
DEV_DEPARTMENT = ("교육운영본부", "교육 운영을 총괄하는 본부")
DEV_TEAM = "교육 1팀"
DEV_POSITIONS = (
    ("팀리드", 1, AssignmentScope.COURSE),
    ("운영 매니저", 2, AssignmentScope.COURSE),
    ("조교", 3, AssignmentScope.COHORT),
    ("러닝 코치", 4, AssignmentScope.COURSE),
)
SEEDABLE_ENVIRONMENTS = ("local", "test")


async def seed_dev_org(settings: Settings) -> list[str]:
    """개발 DB에 부서·팀·직위(담당 방식)를 넣고, 담당 팀이 없는 활성 과정을 팀에 연결한다.

    여러 번 실행해도 결과가 같다(이름으로 찾고 없을 때만 만든다). 직위의 우선순위·담당 방식은
    정의대로 맞춘다. 이미 다른 팀에 연결된 과정은 건드리지 않는다. local·test 환경에서만 실행한다.
    """
    if settings.environment not in SEEDABLE_ENVIRONMENTS:
        raise AppError(
            "개발 데이터는 local·test 환경에서만 넣을 수 있습니다.", code="seed_not_allowed"
        )
    departments, teams = TortoiseDepartmentRepository(), TortoiseTeamRepository()
    positions, links = TortoiseEmployeePositionRepository(), TortoiseBootcampTeamRepository()
    lines: list[str] = []
    async with UnitOfWork():
        name, description = DEV_DEPARTMENT
        department = await departments.get_by_name(name)
        if department is None:
            department = Department(name=name, description=description)
            await departments.add(department)
            lines.append(f"부서: {name}을(를) 만들었습니다.")
        team = await teams.find_by_department_and_name(department.id, DEV_TEAM)
        if team is None:
            team = Team(department_id=department.id, name=DEV_TEAM)
            await teams.add(team)
            lines.append(f"팀: {department.name} > {DEV_TEAM}을(를) 만들었습니다.")
        for position_name, priority, scope in DEV_POSITIONS:
            position = await positions.get_by_name(position_name)
            if position is None:
                await positions.add(
                    EmployeePosition(name=position_name, priority=priority, assignment_scope=scope)
                )
                lines.append(f"직위: {position_name}({scope})을(를) 만들었습니다.")
            elif (position.priority, position.assignment_scope) != (priority, scope):
                position.update(name=position.name, priority=priority, assignment_scope=scope)
                await positions.save(position)
                lines.append(f"직위: {position_name}을(를) {priority}·{scope}로 맞췄습니다.")
        linked = {link.bootcamp_id for link in await links.list_all()}
        for bootcamp in await TortoiseBootcampRepository().list_active():
            if bootcamp.id not in linked:
                await links.assign(bootcamp.id, team.id)
                lines.append(f"과정: {bootcamp.name}을(를) {DEV_TEAM}에 연결했습니다.")
    return lines or ["바꿀 것이 없습니다 (이미 반영됨)."]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="OZ 백오피스 운영 CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-super-admin", help="이메일로 최고 관리자를 등록한다")
    admin.add_argument("email", help="운영진 Google 계정 이메일")
    admin.add_argument("--name", help="회원이 없을 때 만들 이름 (기본: 이메일 앞부분)")
    commands.add_parser("seed-roles", help="역할·권한 정의를 DB에 맞춘다 (멱등)")
    commands.add_parser(
        "seed-dev-org",
        help="개발용 부서·팀·직위와 과정 담당 팀을 넣는다 (멱등, local·test 전용, A62)",
    )
    mail = commands.add_parser("send-test-mail", help="현재 MAIL_DRIVER로 테스트 메일을 보낸다")
    mail.add_argument("to", help="받는 주소")
    commands.add_parser(
        "export-openapi",
        help="OpenAPI 스키마를 표준 출력으로 내보낸다 (프론트 타입 생성용, decisions F19)",
    )
    return parser


def export_openapi(settings: Settings) -> str:
    """서버·DB·Redis 없이 앱 정의에서 스키마를 만든다.

    프론트는 이 결과를 `apps/frontend/openapi.json`으로 커밋하고
    `npm run api:gen`으로 타입을 만든다.
    CI는 다시 내보낸 결과와 커밋된 파일을 비교한다.
    """
    from app.main import create_app  # 앱 조립은 이 명령에서만 필요하다

    schema = create_app(settings).openapi()
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


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
        if args.command == "seed-dev-org":
            return "\n".join(await seed_dev_org(settings))
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
    if args.command == "export-openapi":  # 로그 없이 스키마만 출력한다
        sys.stdout.write(export_openapi(settings))
        return 0
    configure_logging(settings.log_level)  # console 메일 드라이버 출력 등을 보이게 한다
    try:
        print(asyncio.run(_run(args, settings)))
    except AppError as exc:
        print(f"실패: {exc.message} ({exc.code})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

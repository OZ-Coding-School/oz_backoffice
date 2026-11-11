"""FastAPI 애플리케이션 팩토리."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from app.api import health, v1
from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.application.student_claims import StudentClaims
from app.contexts.academy.application.student_queries import StudentQueries
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.access.application.roles import RoleAssignmentService, RoleQueries
from app.contexts.access.infrastructure.repositories import TortoiseUserRoleRepository
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.educator.application.mentor_onboarding import MentorOnboarding
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.infrastructure.repositories import (
    TortoiseEducatorContractRepository,
    TortoiseMentorRepository,
)
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.application.signup_matching import SignupMatcher
from app.contexts.identity.application.user_admin import UserAdministration
from app.contexts.identity.infrastructure.repositories import TortoiseUserRepository
from app.contexts.organization.application.employee_queries import EmployeeQueries
from app.contexts.organization.infrastructure.repositories import TortoiseEmployeeRepository
from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.core.database import build_tortoise_config
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.notifications import build_mail_sender, build_sms_sender
from app.core.redis import create_redis
from app.core.storage import build_s3_storage
from app.workers.broker import broker
from app.workers.tasks.notifications import TaskiqMailDispatcher
from app.workers.tasks.roster import TaskiqRosterSyncDispatcher


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.redis = create_redis(settings.redis_url)
        app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        await broker.startup()  # 작업을 보내는 쪽(API)도 브로커 연결이 필요하다
        try:
            async with RegisterTortoise(
                app,
                config=build_tortoise_config(settings.database_url, with_aerich=False),
            ):
                yield
        finally:
            await broker.shutdown()
            await app.state.http_client.aclose()
            await app.state.redis.aclose()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.clock = clock = SystemClock()
    app.state.storage = build_s3_storage(settings)
    app.state.mail_sender = build_mail_sender(settings)
    app.state.sms_sender = build_sms_sender(settings)
    # 컨텍스트 간 공개 서비스 연결 (composition root). 다른 컨텍스트의 presentation 의존성이
    # 이 서비스를 쓰되 identity.infrastructure를 직접 import하지 않게 한다.
    app.state.user_queries = UserQueries(TortoiseUserRepository())
    app.state.role_queries = RoleQueries(TortoiseUserRoleRepository(), clock)
    app.state.role_assignments = RoleAssignmentService(TortoiseUserRoleRepository())
    app.state.user_admin = UserAdministration(TortoiseUserRepository(), clock)
    app.state.audit_recorder = AuditRecorder(TortoiseAuditLogRepository(), clock)
    app.state.roster_sync_dispatcher = TaskiqRosterSyncDispatcher()
    app.state.employee_queries = EmployeeQueries(TortoiseEmployeeRepository())
    app.state.mail_dispatcher = TaskiqMailDispatcher()
    # 가입 자동 매칭(A31)·승인(A33): academy·educator·access 공개 서비스를 가입 트랜잭션 안에서 쓴다
    app.state.student_claims = StudentClaims(TortoiseStudentRepository())
    app.state.mentor_onboarding = MentorOnboarding(
        contracts=TortoiseEducatorContractRepository(), mentors=TortoiseMentorRepository()
    )
    app.state.signup_matcher = SignupMatcher(
        students=app.state.student_claims,
        mentors=app.state.mentor_onboarding,
        roles=app.state.role_assignments,
    )
    app.state.academy_catalog = AcademyCatalog(
        TortoiseBootcampRepository(), TortoiseCohortRepository()
    )
    # 기수 멘토 배정·멘토 활성화(A35·A36): 멘토링이 educator 멘토를 조회·잠금·활성 변경한다
    app.state.mentor_queries = MentorQueries(TortoiseMentorRepository())
    # 신청 가능 시간 조회(A37): 그 기수 수강 중인지 확인
    app.state.student_queries = StudentQueries(TortoiseStudentRepository())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(v1.router, prefix=settings.api_prefix)
    return app


app = create_app()

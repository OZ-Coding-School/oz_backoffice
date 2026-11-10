"""멘토링 작업 (얇은 래퍼, 로직은 mentoring CohortMentorService).

- `mentoring.assignments.expire`: 매일 00:00 KST, 종료일이 지난 활성 기수 멘토 배정을 비활성화한다
  (decisions A35, 사유 EXPIRED). 멱등이라 워커가 멈췄다가 다시 돌아도 밀린 배정을 모두 처리한다.

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import logging

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.mentoring.application.assignment_service import CohortMentorService
from app.contexts.mentoring.infrastructure.repositories import TortoiseCohortMentorRepository
from app.core.clock import SystemClock
from app.core.uow import UnitOfWork
from app.workers.broker import broker

logger = logging.getLogger(__name__)

DAILY_0000_KST = {"cron": "0 0 * * *", "cron_offset": "Asia/Seoul"}


def build_assignment_service() -> CohortMentorService:
    clock = SystemClock()
    return CohortMentorService(
        assignments=TortoiseCohortMentorRepository(),
        mentors=MentorQueries(TortoiseMentorRepository()),
        cohorts=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


@broker.task(task_name="mentoring.assignments.expire", schedule=[DAILY_0000_KST])
async def expire_assignments() -> None:
    count = await build_assignment_service().expire_ended()
    logger.info("종료일이 지난 기수 멘토 배정 %d건을 비활성화했습니다.", count)

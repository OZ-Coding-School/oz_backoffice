"""멘토링 작업 (얇은 래퍼, 로직은 mentoring CohortMentorService).

- `mentoring.assignments.expire`: 매일 00:00 KST, 종료일이 지난 활성 기수 멘토 배정을 비활성화한다
  (decisions A35, 사유 EXPIRED). 멱등이라 워커가 멈췄다가 다시 돌아도 밀린 배정을 모두 처리한다.
- `mentoring.requests.expire`: 10분마다, 승인 가능한 희망 일시가 남지 않은 대기 신청을 취소하고
  보류 시간을 돌려준다(decisions A42, 멱등).
- `mentoring.meet.create_space`: 승인 커밋 후 보낸다. 세션의 Meet 공간을 만든다
  (최대 3회, 5초·30초 간격).
- `mentoring.meet.sync`: 10분마다, 공간 없는 시작 전 예정 세션에 공간을 만들고 취소된 세션의 공간을
  막는다(A48, 멱등). MEET_DRIVER=disabled이면 아무것도 하지 않는다.
- `mentoring.enrollment_ended.process`: 명단 동기화가 성공하면 보낸다(roster 작업). 수강 중이 아닌
  수강생을 팀에서 빼고 대기 신청·시작 전 1:1 세션을 취소한 뒤 1:1 잔여를 회수한다(A39·A45, 멱등).

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import asyncio
import logging
import uuid

from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.application.student_queries import StudentQueries
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseStudentRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.infrastructure.repositories import TortoiseMentorRepository
from app.contexts.mentoring.application.assignment_service import CohortMentorService
from app.contexts.mentoring.application.availability_service import AvailableTimesService
from app.contexts.mentoring.application.calendar import BusinessCalendar
from app.contexts.mentoring.application.enrollment_ended import EnrollmentEndedService
from app.contexts.mentoring.application.meet_service import MeetSpaceService
from app.contexts.mentoring.application.request_cleanup import RequestCleanup
from app.contexts.mentoring.application.request_service import MentoringRequestService
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentoringSettingsRepository,
    TortoiseCohortMentorRepository,
    TortoiseMentoringBlockTimeRepository,
    TortoiseMentoringHolidayRepository,
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
    TortoiseMentorUnavailablePeriodRepository,
)
from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.meet import build_meet_client
from app.core.uow import UnitOfWork
from app.integrations.google.meet import MeetUnavailableError
from app.workers.broker import broker

logger = logging.getLogger(__name__)

DAILY_0000_KST = {"cron": "0 0 * * *", "cron_offset": "Asia/Seoul"}


def build_cleanup(clock: SystemClock) -> RequestCleanup:
    return RequestCleanup(
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        clock=clock,
    )


def build_assignment_service() -> CohortMentorService:
    clock = SystemClock()
    return CohortMentorService(
        cleanup=build_cleanup(clock),
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


def build_enrollment_ended_service() -> EnrollmentEndedService:
    clock = SystemClock()
    return EnrollmentEndedService(
        teams=TortoiseMentoringTeamRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        cleanup=build_cleanup(clock),
        students=StudentQueries(TortoiseStudentRepository()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


@broker.task(task_name="mentoring.enrollment_ended.process")
async def process_enrollment_ended() -> None:
    result = await build_enrollment_ended_service().process()
    logger.info(
        "수강 종료 처리: 팀원 %d명 제외, 대기 신청 %d건·1:1 세션 %d건 취소, "
        "1:1 계좌 %d개에서 %d분 회수",
        result.removed_members,
        result.canceled_requests,
        result.canceled_sessions,
        result.revoked_accounts,
        result.revoked_minutes,
    )


EVERY_10_MINUTES = {"cron": "*/10 * * * *"}


def build_request_service() -> MentoringRequestService:
    clock = SystemClock()
    mentors = MentorQueries(TortoiseMentorRepository())
    students = StudentQueries(TortoiseStudentRepository())
    availability = AvailableTimesService(
        settings=TortoiseCohortMentoringSettingsRepository(),
        assignments=TortoiseCohortMentorRepository(),
        unavailable_periods=TortoiseMentorUnavailablePeriodRepository(),
        blocks=TortoiseMentoringBlockTimeRepository(),
        calendar=BusinessCalendar(TortoiseMentoringHolidayRepository()),
        mentors=mentors,
        enrollments=students,
        busy=TortoiseMentoringSessionRepository(),
        clock=clock,
    )
    return MentoringRequestService(
        requests=TortoiseMentoringRequestRepository(),
        sessions=TortoiseMentoringSessionRepository(),
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        teams=TortoiseMentoringTeamRepository(),
        settings=TortoiseCohortMentoringSettingsRepository(),
        students=students,
        mentors=mentors,
        availability=availability,
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


@broker.task(task_name="mentoring.requests.expire", schedule=[EVERY_10_MINUTES])
async def expire_requests() -> None:
    count = await build_request_service().expire_stale()
    if count:
        logger.info("승인 기한이 지난 대기 신청 %d건을 취소했습니다.", count)


MEET_ATTEMPTS = 3
MEET_RETRY_DELAYS_SECONDS = (5, 30)


def build_meet_service() -> MeetSpaceService:
    return MeetSpaceService(
        sessions=TortoiseMentoringSessionRepository(),
        meet=build_meet_client(get_settings()),
        uow=UnitOfWork(),
        clock=SystemClock(),
    )


async def create_space_with_retry(
    session_id: uuid.UUID,
    *,
    service: MeetSpaceService | None = None,
    delays: tuple[int, ...] = MEET_RETRY_DELAYS_SECONDS,
) -> bool:
    service = service or build_meet_service()
    for attempt in range(1, MEET_ATTEMPTS + 1):
        try:
            return await service.ensure_space(session_id)
        except MeetUnavailableError:
            logger.warning(
                "Meet 공간 생성 실패 %d/%d (세션 %s)", attempt, MEET_ATTEMPTS, session_id
            )
            if attempt < MEET_ATTEMPTS:
                await asyncio.sleep(delays[min(attempt - 1, len(delays) - 1)])
    return False  # 주기 작업(sync)이 다시 만든다


@broker.task(task_name="mentoring.meet.create_space")
async def create_meet_space(session_id: str) -> None:
    await create_space_with_retry(uuid.UUID(session_id))


@broker.task(task_name="mentoring.meet.sync", schedule=[EVERY_10_MINUTES])
async def sync_meet_spaces() -> None:
    created, closed = await build_meet_service().sync()
    if created or closed:
        logger.info("Meet 공간 %d개 생성, %d개 막음", created, closed)


class TaskiqMeetScheduler:
    """승인 커밋 후 공간 생성을 워커로 보낸다. app.main이 app.state.meet_scheduler에 연결한다."""

    async def space_needed(self, session_id: uuid.UUID) -> None:
        await create_meet_space.kiq(str(session_id))

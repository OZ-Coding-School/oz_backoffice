"""교육 인력 계약 작업 (얇은 래퍼, 로직은 educator ContractService).

- `educator.contracts.expire`: 매일 00:05 KST, 시작일이 된 SIGNED 계약을 ACTIVE로, 종료일이 지난
  ACTIVE 계약을 ENDED로 바꾼다 (decisions A109③). 멱등이라 워커가 멈췄다가 다시 돌아도 밀린 계약을
  모두 처리한다. 끝난 계약을 근거로 한 기수 배정도 함께 끈다(A110).

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import logging

from app.composition.assignment_contracts import AssignmentContractListener
from app.contexts.academy.application.catalog import AcademyCatalog
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.educator.application.contracts import ContractService
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractAmendmentRepository,
    TortoiseContractFileRepository,
    TortoiseEducatorContractRepository,
    TortoiseInstructorRepository,
    TortoiseMentorRepository,
)
from app.contexts.organization.application.employee_queries import EmployeeQueries
from app.contexts.organization.infrastructure.repositories import TortoiseEmployeeRepository
from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.storage import build_s3_storage
from app.core.uow import UnitOfWork
from app.workers.broker import broker

logger = logging.getLogger(__name__)

DAILY_0005_KST = {"cron": "5 0 * * *", "cron_offset": "Asia/Seoul"}


def build_contract_service() -> ContractService:
    clock = SystemClock()
    return ContractService(
        contracts=TortoiseEducatorContractRepository(),
        amendments=TortoiseContractAmendmentRepository(),
        files=TortoiseContractFileRepository(),
        mentors=TortoiseMentorRepository(),
        instructors=TortoiseInstructorRepository(),
        employees=EmployeeQueries(TortoiseEmployeeRepository()),
        academy=AcademyCatalog(TortoiseBootcampRepository(), TortoiseCohortRepository()),
        storage=build_s3_storage(get_settings()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
        listener=AssignmentContractListener(
            audit=AuditRecorder(TortoiseAuditLogRepository(), clock), clock=clock
        ),
    )


@broker.task(task_name="educator.contracts.expire", schedule=[DAILY_0005_KST])
async def expire_contracts() -> None:
    count = await build_contract_service().advance_due()
    logger.info("날짜에 따라 계약 %d건의 상태를 바꿨습니다(SIGNED→ACTIVE, ACTIVE→ENDED).", count)

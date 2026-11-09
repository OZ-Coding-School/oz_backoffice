"""교육 인력 계약 작업 (얇은 래퍼, 로직은 educator ContractService).

- `educator.contracts.expire`: 매일 00:05 KST, 종료일이 지난 ACTIVE 계약을 ENDED로 바꾼다
  (decisions A24). 멱등이라 워커가 멈췄다가 다시 돌아도 밀린 계약을 모두 처리한다.

이 모듈은 composition root라 여러 컨텍스트의 infrastructure를 직접 조립한다.
"""

import logging

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.audit.infrastructure.repositories import TortoiseAuditLogRepository
from app.contexts.educator.application.contracts import ContractService
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractFileRepository,
    TortoiseEducatorContractRepository,
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
        files=TortoiseContractFileRepository(),
        employees=EmployeeQueries(TortoiseEmployeeRepository()),
        storage=build_s3_storage(get_settings()),
        audit=AuditRecorder(TortoiseAuditLogRepository(), clock),
        uow=UnitOfWork(),
        clock=clock,
    )


@broker.task(task_name="educator.contracts.expire", schedule=[DAILY_0005_KST])
async def expire_contracts() -> None:
    count = await build_contract_service().expire_ended()
    logger.info("기간이 끝난 계약 %d건을 ENDED로 바꿨습니다.", count)

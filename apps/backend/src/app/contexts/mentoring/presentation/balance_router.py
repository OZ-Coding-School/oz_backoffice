"""멘토링 시간 계좌 API (decisions M8·M9·A39·A40).

mentoring.balance.grant (기수 범위, 매니저·조교):
  GET    /admin/cohorts/{cohort_id}/mentoring-balances?owner=&limit=&offset=
  POST   /admin/cohorts/{cohort_id}/mentoring-balances/grants              (Idempotency-Key 필수)
  PATCH  /admin/cohorts/{cohort_id}/mentoring-balances/{account_id}        (사용 기간)
  POST   /admin/cohorts/{cohort_id}/mentoring-balances/{account_id}/adjustments  (Idempotency-Key)
  GET    /admin/cohorts/{cohort_id}/mentoring-balances/{account_id}/transactions?before=&limit=
본인:
  GET    /me/balances                              (1:1 계좌 + 소속 팀 계좌)
  GET    /me/balances/{account_id}/transactions
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import ApprovedUser, require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.balance_service import (
    BalanceService,
    CohortLookup,
    GrantTarget,
    Owners,
    StudentLookup,
)
from app.contexts.mentoring.domain.balance import (
    REASON_MAX_LENGTH,
    BalanceAccount,
    BalanceTransaction,
)
from app.contexts.mentoring.domain.enums import MentoringBalanceTransactionType
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseBalanceAccountRepository,
    TortoiseBalanceTransactionRepository,
    TortoiseCohortMentoringSettingsRepository,
    TortoiseMentoringTeamRepository,
)
from app.core.clock import Clock
from app.core.dependencies import get_clock
from app.core.idempotency import RedisIdempotency
from app.core.pagination import Page
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.shared.time import business_date

admin_router = APIRouter(
    prefix="/admin/cohorts/{cohort_id}/mentoring-balances", tags=["admin-mentoring-balances"]
)
me_router = APIRouter(prefix="/me/balances", tags=["mentoring-balances"])

BalanceManager = Annotated[
    User, Depends(require_permission("mentoring.balance.manage", cohort_param="cohort_id"))
]
BalanceReader = Annotated[
    User, Depends(require_permission("mentoring.balance.read", cohort_param="cohort_id"))
]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
        description="요청마다 프론트가 만든 고유 ID. 같은 ID로 다시 보내면 첫 응답(24시간)",
    ),
]
OwnerType = Literal["STUDENT", "TEAM"]


def get_balance_service(
    request: Request, clock: Annotated[Clock, Depends(get_clock)]
) -> BalanceService:
    state = request.app.state
    return BalanceService(
        accounts=TortoiseBalanceAccountRepository(),
        ledger=TortoiseBalanceTransactionRepository(),
        teams=TortoiseMentoringTeamRepository(),
        settings=TortoiseCohortMentoringSettingsRepository(),
        students=cast("StudentLookup", state.student_queries),
        cohorts=cast("CohortLookup", state.academy_catalog),
        audit=cast("AuditRecorder", state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


def get_idempotency(redis: Annotated[Any, Depends(get_redis)]) -> RedisIdempotency:
    return RedisIdempotency(redis)


ServiceDep = Annotated[BalanceService, Depends(get_balance_service)]
IdempotencyDep = Annotated[RedisIdempotency, Depends(get_idempotency)]
ClockDep = Annotated[Clock, Depends(get_clock)]


# ---------------------------------------------------------------- 스키마
class AccountResponse(BaseModel):
    id: uuid.UUID
    owner_type: OwnerType
    owner_id: uuid.UUID = Field(description="수강생(students.id) 또는 팀 ID")
    owner_name: str = Field(description="수강생 이름 또는 팀 이름(없으면 'N팀')")
    valid_from: date
    valid_until: date
    is_expired: bool
    total_minutes: int
    held_minutes: int
    used_minutes: int
    remaining_minutes: int


class TransactionResponse(BaseModel):
    id: uuid.UUID
    type: MentoringBalanceTransactionType
    amount: int = Field(description="분 (조정만 음수 가능)")
    after_remaining: int
    after_held: int
    reason: str
    created_at: datetime | None

    @classmethod
    def of(cls, e: BalanceTransaction) -> "TransactionResponse":
        return cls(
            id=e.id,
            type=e.type,
            amount=e.amount,
            after_remaining=e.after_remaining,
            after_held=e.after_held,
            reason=e.reason,
            created_at=e.created_at,
        )


class GrantRequest(BaseModel):
    target: GrantTarget = Field(
        description="ALL_STUDENTS(기수 전체 수강 중) / STUDENTS / ALL_TEAMS(기수 전체) / TEAMS"
    )
    ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=500, description="STUDENTS·TEAMS일 때 대상 ID"
    )
    minutes: int | None = Field(
        default=None, description="60분 단위. 비우면 기수 설정의 기본 지급 시간"
    )
    valid_from: date | None = Field(
        default=None, description="새 계좌 사용 시작일 (기본: 기수 시작일)"
    )
    valid_until: date | None = Field(
        default=None, description="새 계좌 사용 종료일 (기본: 기수 종료일)"
    )
    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)


class GrantedResponse(BaseModel):
    owner_id: uuid.UUID
    account_id: uuid.UUID
    minutes: int
    created: bool = Field(description="이번 지급으로 계좌를 만들었는지")


class SkippedResponse(BaseModel):
    owner_id: uuid.UUID
    code: str
    message: str


class GrantResponse(BaseModel):
    granted: list[GrantedResponse]
    skipped: list[SkippedResponse] = Field(description="지급하지 못한 대상과 사유")


class AdjustRequest(BaseModel):
    minutes: int = Field(description="60분 단위, ± (만료 계좌는 음수만)")
    reason: str = Field(min_length=1, max_length=REASON_MAX_LENGTH)


class ValidityRequest(BaseModel):
    valid_from: date
    valid_until: date


def _accounts(accounts: list[BalanceAccount], owners: Owners, today: date) -> list[AccountResponse]:
    items = []
    for a in accounts:
        if a.team_id is not None:
            team = owners.teams.get(a.team_id)
            owner_type: OwnerType = "TEAM"
            owner_id, name = a.team_id, team.label if team else ""
        else:
            student = owners.students.get(a.student_id) if a.student_id else None
            owner_type = "STUDENT"
            owner_id, name = cast("uuid.UUID", a.student_id), student.name if student else ""
        items.append(
            AccountResponse(
                id=a.id,
                owner_type=owner_type,
                owner_id=owner_id,
                owner_name=name,
                valid_from=a.valid_from,
                valid_until=a.valid_until,
                is_expired=a.is_expired(today),
                total_minutes=a.total_minutes,
                held_minutes=a.held_minutes,
                used_minutes=a.used_minutes,
                remaining_minutes=a.remaining_minutes,
            )
        )
    return items


async def _one(service: BalanceService, account: BalanceAccount, clock: Clock) -> AccountResponse:
    owners = await service.owners_of([account])
    return _accounts([account], owners, business_date(clock.now()))[0]


Limit = Annotated[int, Query(ge=1, le=100)]
Before = Annotated[uuid.UUID | None, Query(description="이 원장 ID보다 이전 (커서)")]


# ---------------------------------------------------------------- 운영진
@admin_router.get("", response_model=Page[AccountResponse])
async def list_accounts(
    cohort_id: uuid.UUID,
    _: BalanceReader,
    service: ServiceDep,
    clock: ClockDep,
    owner: OwnerType | None = None,
    limit: Limit = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AccountResponse]:
    accounts, total = await service.list_accounts(
        cohort_id, owner=owner, limit=limit, offset=offset
    )
    owners = await service.owners_of(accounts)
    items = _accounts(accounts, owners, business_date(clock.now()))
    return Page(items=items, total=total, limit=limit, offset=offset)


@admin_router.post("/grants", response_model=GrantResponse)
async def grant(
    cohort_id: uuid.UUID,
    body: GrantRequest,
    user: BalanceManager,
    service: ServiceDep,
    idempotency: IdempotencyDep,
    key: IdempotencyKey,
) -> GrantResponse:
    """개별·일괄 지급. 가능한 대상만 지급하고 나머지는 `skipped`에 사유와 함께 준다."""

    async def run() -> GrantResponse:
        result = await service.grant(
            cohort_id,
            target=body.target,
            ids=body.ids,
            minutes=body.minutes,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            reason=body.reason,
            actor_id=user.id,
        )
        return GrantResponse(
            granted=[
                GrantedResponse(
                    owner_id=g.owner_id,
                    account_id=g.account_id,
                    minutes=g.minutes,
                    created=g.created,
                )
                for g in result.granted
            ],
            skipped=[
                SkippedResponse(owner_id=s.owner_id, code=s.code, message=s.message)
                for s in result.skipped
            ],
        )

    return await idempotency.run(f"balance-grant:{user.id}:{cohort_id}", key, GrantResponse, run)


@admin_router.patch("/{account_id}", response_model=AccountResponse)
async def change_validity(
    cohort_id: uuid.UUID,
    account_id: uuid.UUID,
    body: ValidityRequest,
    user: BalanceManager,
    service: ServiceDep,
    clock: ClockDep,
) -> AccountResponse:
    """사용 기간 수정 (기수 기간 안, A40)."""
    account = await service.change_validity(
        cohort_id, account_id, body.valid_from, body.valid_until, actor_id=user.id
    )
    return await _one(service, account, clock)


@admin_router.post("/{account_id}/adjustments", response_model=AccountResponse)
async def adjust(
    cohort_id: uuid.UUID,
    account_id: uuid.UUID,
    body: AdjustRequest,
    user: BalanceManager,
    service: ServiceDep,
    clock: ClockDep,
    idempotency: IdempotencyDep,
    key: IdempotencyKey,
) -> AccountResponse:
    async def run() -> AccountResponse:
        account = await service.adjust(
            cohort_id, account_id, body.minutes, body.reason, actor_id=user.id
        )
        return await _one(service, account, clock)

    return await idempotency.run(
        f"balance-adjust:{user.id}:{account_id}", key, AccountResponse, run
    )


@admin_router.get("/{account_id}/transactions", response_model=list[TransactionResponse])
async def list_transactions(
    cohort_id: uuid.UUID,
    account_id: uuid.UUID,
    _: BalanceReader,
    service: ServiceDep,
    before: Before = None,
    limit: Limit = 50,
) -> list[TransactionResponse]:
    """원장 (최신순, 커서 페이지네이션)."""
    entries = await service.transactions(cohort_id, account_id, before=before, limit=limit)
    return [TransactionResponse.of(e) for e in entries]


# ---------------------------------------------------------------- 본인
@me_router.get("", response_model=list[AccountResponse])
async def my_accounts(
    user: ApprovedUser, service: ServiceDep, clock: ClockDep
) -> list[AccountResponse]:
    """본인 1:1 계좌와 소속 팀 계좌 (A39)."""
    accounts = await service.mine(user.id)
    owners = await service.owners_of(accounts)
    return _accounts(accounts, owners, business_date(clock.now()))


@me_router.get("/{account_id}/transactions", response_model=list[TransactionResponse])
async def my_transactions(
    account_id: uuid.UUID,
    user: ApprovedUser,
    service: ServiceDep,
    before: Before = None,
    limit: Limit = 50,
) -> list[TransactionResponse]:
    entries = await service.my_transactions(user.id, account_id, before=before, limit=limit)
    return [TransactionResponse.of(e) for e in entries]

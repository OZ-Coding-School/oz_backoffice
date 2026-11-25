"""학사 마스터 관리 API (HRD 과정·회차, 운영과정, 기수). 권한: org.manage (전체 범위).

PATCH는 보낸 필드만 바꾼다(null을 보내면 그 값을 비운다). 소속 FK는 바꿀 수 없다.
"""

import uuid
from datetime import date
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.contexts.academy.application.academy_admin import AcademyAdminService
from app.contexts.academy.application.cohort_summary import CohortSummary, CohortSummaryReader
from app.contexts.academy.domain.enums import (
    CohortStatus,
    DayNightSeType,
    HRDNetTrainType,
    WeekendSeType,
)
from app.contexts.academy.infrastructure.repositories import (
    TortoiseBootcampRepository,
    TortoiseCohortRepository,
    TortoiseHrdNetBootcampCohortRepository,
    TortoiseHrdNetBootcampRepository,
)
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.identity.domain.entities import User
from app.core.uow import UnitOfWork

router = APIRouter(prefix="/admin", tags=["admin-academy"])


def get_academy_admin_service(request: Request) -> AcademyAdminService:
    return AcademyAdminService(
        hrd_bootcamps=TortoiseHrdNetBootcampRepository(),
        hrd_cohorts=TortoiseHrdNetBootcampCohortRepository(),
        bootcamps=TortoiseBootcampRepository(),
        cohorts=TortoiseCohortRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )


HrdReader = Annotated[User, Depends(require_permission("academy.hrd.read"))]
HrdManager = Annotated[User, Depends(require_permission("academy.hrd.manage"))]
BootcampReader = Annotated[User, Depends(require_permission("academy.bootcamp.read"))]
BootcampManager = Annotated[User, Depends(require_permission("academy.bootcamp.manage"))]
BootcampCohortReader = Annotated[
    User, Depends(require_permission("academy.cohort.read", bootcamp_param="bootcamp_id"))
]
BootcampCohortManager = Annotated[
    User, Depends(require_permission("academy.cohort.manage", bootcamp_param="bootcamp_id"))
]
CohortReader = Annotated[
    User, Depends(require_permission("academy.cohort.read", cohort_param="cohort_id"))
]
CohortManager = Annotated[
    User, Depends(require_permission("academy.cohort.manage", cohort_param="cohort_id"))
]
ServiceDep = Annotated[AcademyAdminService, Depends(get_academy_admin_service)]
NonNegative = Annotated[int, Field(ge=0)]
SmallPositive = Annotated[int, Field(ge=1, le=32767)]


def _sent(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


# ---------------------------------------------------------------- 스키마
class _FromEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HrdBootcampFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    hrd_net_id: str | None = Field(default=None, max_length=100)
    train_type: HRDNetTrainType | None = None
    ncs1_se: str | None = Field(default=None, max_length=10)
    ncs2_se: str | None = Field(default=None, max_length=10)
    ncs3_se: str | None = Field(default=None, max_length=10)
    weekend_se: WeekendSeType = WeekendSeType.WEEKDAY
    day_night_se: DayNightSeType = DayNightSeType.DAY
    total_train_fee: NonNegative | None = None
    train_fee_per_hour: NonNegative | None = None
    total_train_hours: NonNegative | None = None
    total_train_days: NonNegative | None = None


class HrdBootcampUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    hrd_net_id: str | None = Field(default=None, max_length=100)
    train_type: HRDNetTrainType | None = None
    ncs1_se: str | None = Field(default=None, max_length=10)
    ncs2_se: str | None = Field(default=None, max_length=10)
    ncs3_se: str | None = Field(default=None, max_length=10)
    weekend_se: WeekendSeType | None = None
    day_night_se: DayNightSeType | None = None
    total_train_fee: NonNegative | None = None
    train_fee_per_hour: NonNegative | None = None
    total_train_hours: NonNegative | None = None
    total_train_days: NonNegative | None = None


class HrdBootcampResponse(HrdBootcampFields, _FromEntity):
    id: uuid.UUID


class HrdCohortFields(BaseModel):
    cohort_number: SmallPositive
    train_start_date: date | None = None
    train_end_date: date | None = None
    self_pay_amount: NonNegative | None = None


class HrdCohortUpdate(BaseModel):
    cohort_number: SmallPositive | None = None
    train_start_date: date | None = None
    train_end_date: date | None = None
    self_pay_amount: NonNegative | None = None


class HrdCohortResponse(HrdCohortFields, _FromEntity):
    id: uuid.UUID
    hrd_net_bootcamp_id: uuid.UUID


class BootcampCreate(BaseModel):
    hrd_net_bootcamp_id: uuid.UUID
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=20)
    is_active: bool = True
    airtable_cohort_prefix: str | None = Field(default=None, max_length=50)


class BootcampUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None
    airtable_cohort_prefix: str | None = Field(default=None, max_length=50)


class BootcampResponse(_FromEntity):
    id: uuid.UUID
    hrd_net_bootcamp_id: uuid.UUID
    name: str
    code: str
    is_active: bool
    airtable_cohort_prefix: str | None


class CohortCreate(BaseModel):
    hrd_net_cohort_id: uuid.UUID
    cohort_number: SmallPositive
    start_date: date
    end_date: date
    status: CohortStatus = CohortStatus.PLANNED
    discord_guild_id: str | None = Field(default=None, max_length=32, pattern=r"^\d+$")


class CohortUpdate(BaseModel):
    hrd_net_cohort_id: uuid.UUID | None = None
    cohort_number: SmallPositive | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: CohortStatus | None = None
    discord_guild_id: str | None = Field(default=None, max_length=32, pattern=r"^\d+$")


class CohortResponse(_FromEntity):
    id: uuid.UUID
    bootcamp_id: uuid.UUID
    hrd_net_cohort_id: uuid.UUID
    cohort_number: int
    start_date: date
    end_date: date
    status: CohortStatus
    discord_guild_id: str | None


def _not_null(changes: dict[str, Any], *fields: str) -> dict[str, Any]:
    """비울 수 없는 필드에 null을 보내면 무시한다 (선택 필드처럼 다룬다)."""
    return {k: v for k, v in changes.items() if not (k in fields and v is None)}


# ---------------------------------------------------------------- HRD 과정
@router.get("/hrd-bootcamps", response_model=list[HrdBootcampResponse])
async def list_hrd_bootcamps(_: HrdReader, service: ServiceDep) -> list[HrdBootcampResponse]:
    return [HrdBootcampResponse.model_validate(b) for b in await service.list_hrd_bootcamps()]


@router.post(
    "/hrd-bootcamps", response_model=HrdBootcampResponse, status_code=status.HTTP_201_CREATED
)
async def create_hrd_bootcamp(
    body: HrdBootcampFields, admin: HrdManager, service: ServiceDep
) -> HrdBootcampResponse:
    created = await service.create_hrd_bootcamp(body.model_dump(), actor_id=admin.id)
    return HrdBootcampResponse.model_validate(created)


@router.get("/hrd-bootcamps/{hrd_bootcamp_id}", response_model=HrdBootcampResponse)
async def get_hrd_bootcamp(
    hrd_bootcamp_id: uuid.UUID, _: HrdReader, service: ServiceDep
) -> HrdBootcampResponse:
    return HrdBootcampResponse.model_validate(await service.get_hrd_bootcamp(hrd_bootcamp_id))


@router.patch("/hrd-bootcamps/{hrd_bootcamp_id}", response_model=HrdBootcampResponse)
async def update_hrd_bootcamp(
    hrd_bootcamp_id: uuid.UUID, body: HrdBootcampUpdate, admin: HrdManager, service: ServiceDep
) -> HrdBootcampResponse:
    changes = _not_null(_sent(body), "name", "weekend_se", "day_night_se")
    updated = await service.update_hrd_bootcamp(hrd_bootcamp_id, changes, actor_id=admin.id)
    return HrdBootcampResponse.model_validate(updated)


@router.delete("/hrd-bootcamps/{hrd_bootcamp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hrd_bootcamp(
    hrd_bootcamp_id: uuid.UUID, admin: HrdManager, service: ServiceDep
) -> Response:
    """운영과정·HRD 회차가 참조 중이면 409 in_use."""
    await service.delete_hrd_bootcamp(hrd_bootcamp_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- HRD 회차
@router.get("/hrd-bootcamps/{hrd_bootcamp_id}/cohorts", response_model=list[HrdCohortResponse])
async def list_hrd_cohorts(
    hrd_bootcamp_id: uuid.UUID, _: HrdReader, service: ServiceDep
) -> list[HrdCohortResponse]:
    return [
        HrdCohortResponse.model_validate(c) for c in await service.list_hrd_cohorts(hrd_bootcamp_id)
    ]


@router.post(
    "/hrd-bootcamps/{hrd_bootcamp_id}/cohorts",
    response_model=HrdCohortResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_hrd_cohort(
    hrd_bootcamp_id: uuid.UUID, body: HrdCohortFields, admin: HrdManager, service: ServiceDep
) -> HrdCohortResponse:
    created = await service.create_hrd_cohort(hrd_bootcamp_id, body.model_dump(), actor_id=admin.id)
    return HrdCohortResponse.model_validate(created)


@router.patch("/hrd-cohorts/{hrd_cohort_id}", response_model=HrdCohortResponse)
async def update_hrd_cohort(
    hrd_cohort_id: uuid.UUID, body: HrdCohortUpdate, admin: HrdManager, service: ServiceDep
) -> HrdCohortResponse:
    changes = _not_null(_sent(body), "cohort_number")
    updated = await service.update_hrd_cohort(hrd_cohort_id, changes, actor_id=admin.id)
    return HrdCohortResponse.model_validate(updated)


@router.delete("/hrd-cohorts/{hrd_cohort_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hrd_cohort(
    hrd_cohort_id: uuid.UUID, admin: HrdManager, service: ServiceDep
) -> Response:
    """기수가 참조 중이면 409 in_use."""
    await service.delete_hrd_cohort(hrd_cohort_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 운영과정
@router.get("/bootcamps", response_model=list[BootcampResponse])
async def list_bootcamps(
    _: BootcampReader, service: ServiceDep, include_inactive: bool = False
) -> list[BootcampResponse]:
    """운영과정 목록. 기본은 활성 과정만."""
    bootcamps = await service.list_bootcamps(include_inactive=include_inactive)
    return [BootcampResponse.model_validate(b) for b in bootcamps]


@router.post("/bootcamps", response_model=BootcampResponse, status_code=status.HTTP_201_CREATED)
async def create_bootcamp(
    body: BootcampCreate, admin: BootcampManager, service: ServiceDep
) -> BootcampResponse:
    created = await service.create_bootcamp(body.model_dump(), actor_id=admin.id)
    return BootcampResponse.model_validate(created)


@router.get("/bootcamps/{bootcamp_id}", response_model=BootcampResponse)
async def get_bootcamp(
    bootcamp_id: uuid.UUID, _: BootcampReader, service: ServiceDep
) -> BootcampResponse:
    return BootcampResponse.model_validate(await service.get_bootcamp(bootcamp_id))


@router.patch("/bootcamps/{bootcamp_id}", response_model=BootcampResponse)
async def update_bootcamp(
    bootcamp_id: uuid.UUID, body: BootcampUpdate, admin: BootcampManager, service: ServiceDep
) -> BootcampResponse:
    """이름·코드·활성 여부·Airtable 기수 별칭. 운영을 멈출 때는 삭제 대신 is_active=false.

    airtable_cohort_prefix를 null로 보내면 명단 동기화 대상에서 뺀다.
    """
    changes = _not_null(_sent(body), "name", "code", "is_active")
    updated = await service.update_bootcamp(bootcamp_id, changes, actor_id=admin.id)
    return BootcampResponse.model_validate(updated)


@router.delete("/bootcamps/{bootcamp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bootcamp(
    bootcamp_id: uuid.UUID, admin: BootcampManager, service: ServiceDep
) -> Response:
    """기수·담당자가 있으면 409 in_use."""
    await service.delete_bootcamp(bootcamp_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- 기수
@router.get("/bootcamps/{bootcamp_id}/cohorts", response_model=list[CohortResponse])
async def list_cohorts(
    bootcamp_id: uuid.UUID, _: BootcampCohortReader, service: ServiceDep
) -> list[CohortResponse]:
    return [CohortResponse.model_validate(c) for c in await service.list_cohorts(bootcamp_id)]


@router.post(
    "/bootcamps/{bootcamp_id}/cohorts",
    response_model=CohortResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cohort(
    bootcamp_id: uuid.UUID, body: CohortCreate, admin: BootcampCohortManager, service: ServiceDep
) -> CohortResponse:
    """기수는 HRD 회차에 연결한다 (운영과정의 대표 HRD 과정과 달라도 된다, decisions D6)."""
    created = await service.create_cohort(bootcamp_id, body.model_dump(), actor_id=admin.id)
    return CohortResponse.model_validate(created)


@router.get("/cohorts/{cohort_id}", response_model=CohortResponse)
async def get_cohort(cohort_id: uuid.UUID, _: CohortReader, service: ServiceDep) -> CohortResponse:
    return CohortResponse.model_validate(await service.get_cohort(cohort_id))


class CohortStudentCountsResponse(BaseModel):
    total: int
    linked: int = Field(description="가입해 회원과 연결된 수강생")
    by_status: dict[str, int] = Field(description="수강 상태(EnrollmentStatus)별 수")


class CohortSummaryMentorResponse(BaseModel):
    mentor_id: uuid.UUID
    name: str
    start_date: date


class CohortSummaryStaffResponse(BaseModel):
    employee_id: uuid.UUID
    name: str
    position_name: str | None
    scope: Literal["COHORT", "COURSE"] = Field(description="기수 담당 / 과정 담당")


class CohortSummaryResponse(BaseModel):
    students: CohortStudentCountsResponse
    mentors: list[CohortSummaryMentorResponse]
    staff: list[CohortSummaryStaffResponse]

    @classmethod
    def of(cls, s: CohortSummary) -> "CohortSummaryResponse":
        return cls(
            students=CohortStudentCountsResponse(
                total=s.students.total, linked=s.students.linked, by_status=s.students.by_status
            ),
            mentors=[
                CohortSummaryMentorResponse(
                    mentor_id=m.mentor_id, name=m.name, start_date=m.start_date
                )
                for m in s.mentors
            ],
            staff=[
                CohortSummaryStaffResponse(
                    employee_id=x.employee_id,
                    name=x.name,
                    position_name=x.position_name,
                    scope=x.scope,
                )
                for x in s.staff
            ],
        )


@router.get("/cohorts/{cohort_id}/summary", response_model=CohortSummaryResponse)
async def get_cohort_summary(
    cohort_id: uuid.UUID, _: CohortReader, service: ServiceDep, request: Request
) -> CohortSummaryResponse:
    """수강생 상태별 인원·활성 배정 멘토·담당자(기수·과정 담당) (A96)."""
    cohort = await service.get_cohort(cohort_id)
    reader = cast("CohortSummaryReader", request.app.state.cohort_summary)
    return CohortSummaryResponse.of(await reader.summary_of(cohort.id, cohort.bootcamp_id))


@router.patch("/cohorts/{cohort_id}", response_model=CohortResponse)
async def update_cohort(
    cohort_id: uuid.UUID, body: CohortUpdate, admin: CohortManager, service: ServiceDep
) -> CohortResponse:
    changes = _not_null(
        _sent(body), "hrd_net_cohort_id", "cohort_number", "start_date", "end_date", "status"
    )
    updated = await service.update_cohort(cohort_id, changes, actor_id=admin.id)
    return CohortResponse.model_validate(updated)


@router.delete("/cohorts/{cohort_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cohort(
    cohort_id: uuid.UUID, admin: CohortManager, service: ServiceDep
) -> Response:
    """수강생·담당자가 있으면 409 in_use. 운영이 끝나면 상태를 ENDED·ARCHIVED로 바꾼다."""
    await service.delete_cohort(cohort_id, actor_id=admin.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

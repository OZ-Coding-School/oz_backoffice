"""교육 인력 계약·계약서 관리 API. 권한: contract.manage (범위 없음 → ANY, decisions A16).

- 계약서 업로드: POST /contract-files/uploads → 브라우저가 S3로 직접 업로드
  → POST /contract-files/uploads/{upload_id}/confirm
- 계약: 목록·생성·조회·수정(DRAFT만, 확정 후 담당 직원만)·삭제(DRAFT만)·확정·해지·계약서 URL
- 응답에 담당 직원 이름·연결된 프로필 이름, 목록 `mentor_id` 필터, 담당 직원 후보 (A103)
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.contract_files import ContractFileUploadService
from app.contexts.educator.application.contract_people import (
    ContractPeople,
    ContractPeopleReader,
    LinkedPerson,
)
from app.contexts.educator.application.contracts import ContractService, ContractView
from app.contexts.educator.application.ports import EmployeeDirectory
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.pending_uploads import RedisPendingUploadStore
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractFileRepository,
    TortoiseEducatorContractRepository,
    TortoiseInstructorRepository,
    TortoiseMentorRepository,
)
from app.contexts.identity.domain.entities import User
from app.core.clock import Clock
from app.core.dependencies import get_clock, get_file_storage
from app.core.pagination import Page
from app.core.redis import get_redis
from app.core.uow import UnitOfWork
from app.integrations.s3 import S3Storage
from app.shared.errors import BusinessRuleViolation

router = APIRouter(prefix="/admin", tags=["admin-contracts"])

Manager = Annotated[User, Depends(require_permission("educator.contract.manage", any_scope=True))]
Reader = Annotated[User, Depends(require_permission("educator.contract.read", any_scope=True))]


def get_contract_service(
    request: Request,
    storage: Annotated[S3Storage, Depends(get_file_storage)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ContractService:
    return ContractService(
        contracts=TortoiseEducatorContractRepository(),
        files=TortoiseContractFileRepository(),
        mentors=TortoiseMentorRepository(),
        instructors=TortoiseInstructorRepository(),
        employees=cast("EmployeeDirectory", request.app.state.employee_queries),
        storage=storage,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
    )


def get_direct_uploads(
    storage: Annotated[S3Storage, Depends(get_file_storage)],
    redis: Annotated[Any, Depends(get_redis)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> DirectUploads:
    return DirectUploads(storage=storage, pending=RedisPendingUploadStore(redis), clock=clock)


def get_upload_service(
    request: Request, uploads: Annotated[DirectUploads, Depends(get_direct_uploads)]
) -> ContractFileUploadService:
    return ContractFileUploadService(
        uploads=uploads,
        files=TortoiseContractFileRepository(),
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
    )


ContractsDep = Annotated[ContractService, Depends(get_contract_service)]


def get_contract_people(request: Request) -> ContractPeopleReader:
    return cast("ContractPeopleReader", request.app.state.contract_people)


PeopleDep = Annotated[ContractPeopleReader, Depends(get_contract_people)]
UploadsDep = Annotated[ContractFileUploadService, Depends(get_upload_service)]


# ---------------------------------------------------------------- 스키마
class UploadRequest(BaseModel):
    file_name: str = Field(min_length=1, description="원본 파일 이름 (PDF, 100자 이하)")


class UploadTicketResponse(BaseModel):
    upload_id: uuid.UUID
    url: str
    fields: dict[str, str] = Field(description="multipart/form-data에 모두 넣고 파일은 `file`로")
    expires_at: datetime
    max_bytes: int


class ContractFileResponse(BaseModel):
    id: uuid.UUID
    file_name: str
    file_size: int
    created_at: datetime | None

    @classmethod
    def of(cls, file: ContractFile) -> "ContractFileResponse":
        return cls(
            id=file.id,
            file_name=file.file_name,
            file_size=file.file_size,
            created_at=file.created_at,
        )


class ContractFields(BaseModel):
    educator_type: EducatorType
    contractor_name: str = Field(min_length=1, max_length=50)
    contractor_phone: str = Field(min_length=1, max_length=20)
    contractor_email: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    manager_employee_id: uuid.UUID
    contract_file_id: uuid.UUID | None = None


class ContractUpdate(BaseModel):
    """보낸 필드만 바꾼다. 확정된 계약은 manager_employee_id만 바꿀 수 있다."""

    educator_type: EducatorType | None = None
    contractor_name: str | None = Field(default=None, min_length=1, max_length=50)
    contractor_phone: str | None = Field(default=None, min_length=1, max_length=20)
    contractor_email: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    manager_employee_id: uuid.UUID | None = None
    contract_file_id: uuid.UUID | None = None


# null을 보내면 비우는 필드 (나머지는 null이면 무시하지 않고 422)
_NULLABLE = frozenset({"contractor_email", "contract_file_id"})


class LinkedProfileResponse(BaseModel):
    name: str = Field(description="실명")
    display_name: str = Field(description="수강생에게 보이는 이름")

    @classmethod
    def of(cls, person: LinkedPerson | None) -> "LinkedProfileResponse | None":
        return cls(name=person.name, display_name=person.display_name) if person else None


class ContractResponse(BaseModel):
    id: uuid.UUID
    educator_type: EducatorType
    status: ContractStatus
    contractor_name: str
    contractor_phone: str
    contractor_email: str | None
    title: str
    start_date: date
    end_date: date
    manager_employee_id: uuid.UUID
    manager_name: str | None = Field(description="담당 직원 이름 (A103)")
    mentor_id: uuid.UUID | None
    instructor_id: uuid.UUID | None
    linked_profile: LinkedProfileResponse | None = Field(
        description="연결된 멘토·강사 프로필 이름 (A103)"
    )
    contract_file: ContractFileResponse | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def of(cls, view: ContractView, people: ContractPeople) -> "ContractResponse":
        c = view.contract
        linked = (
            people.mentors.get(c.mentor_id)
            if c.mentor_id
            else people.instructors.get(c.instructor_id)
            if c.instructor_id
            else None
        )
        return cls(
            id=c.id,
            educator_type=c.educator_type,
            status=c.status,
            contractor_name=c.contractor_name,
            contractor_phone=c.contractor_phone,
            contractor_email=c.contractor_email,
            title=c.title,
            start_date=c.start_date,
            end_date=c.end_date,
            manager_employee_id=c.manager_employee_id,
            manager_name=people.managers.get(c.manager_employee_id),
            mentor_id=c.mentor_id,
            instructor_id=c.instructor_id,
            linked_profile=LinkedProfileResponse.of(linked),
            contract_file=ContractFileResponse.of(view.file) if view.file else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )


class ContractLink(BaseModel):
    """멘토 계약이면 mentor_id, 강사 계약이면 instructor_id 하나만 보낸다."""

    mentor_id: uuid.UUID | None = None
    instructor_id: uuid.UUID | None = None


class ManagerCandidateResponse(BaseModel):
    employee_id: uuid.UUID
    name: str
    email: str
    department_name: str
    team_name: str | None
    position_name: str
    is_me: bool = Field(description="요청한 본인")


async def _one(view: ContractView, people: ContractPeopleReader) -> ContractResponse:
    return ContractResponse.of(view, await people.people([view.contract]))


class FileUrlResponse(BaseModel):
    url: str
    file: ContractFileResponse


# ---------------------------------------------------------------- 계약서 업로드
@router.post(
    "/contract-files/uploads",
    response_model=UploadTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_contract_upload(
    body: UploadRequest, user: Manager, uploads: UploadsDep
) -> UploadTicketResponse:
    ticket = await uploads.request_upload(body.file_name, actor_id=user.id)
    return UploadTicketResponse(
        upload_id=ticket.upload_id,
        url=ticket.url,
        fields=ticket.fields,
        expires_at=ticket.expires_at,
        max_bytes=ticket.max_bytes,
    )


@router.post(
    "/contract-files/uploads/{upload_id}/confirm",
    response_model=ContractFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_contract_upload(
    upload_id: uuid.UUID, user: Manager, uploads: UploadsDep
) -> ContractFileResponse:
    return ContractFileResponse.of(await uploads.confirm(upload_id, actor_id=user.id))


# ---------------------------------------------------------------- 계약
@router.get("/contracts", response_model=Page[ContractResponse])
async def list_contracts(
    _: Reader,
    contracts: ContractsDep,
    people: PeopleDep,
    status_: Annotated[list[ContractStatus] | None, Query(alias="status")] = None,
    educator_type: EducatorType | None = None,
    q: Annotated[str | None, Query(max_length=50, description="계약자 이름·제목·휴대폰")] = None,
    mentor_id: Annotated[uuid.UUID | None, Query(description="연결된 멘토 (A103)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ContractResponse]:
    contract_filter = ContractFilter(
        statuses=frozenset(status_ or ()),
        educator_type=educator_type,
        query=q.strip() if q and q.strip() else None,
        mentor_id=mentor_id,
    )
    views, total = await contracts.list_contracts(contract_filter, limit=limit, offset=offset)
    found = await people.people([v.contract for v in views])
    return Page(
        items=[ContractResponse.of(v, found) for v in views],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/contracts/manager-candidates", response_model=list[ManagerCandidateResponse])
async def contract_manager_candidates(
    user: Manager,
    people: PeopleDep,
    q: Annotated[str | None, Query(max_length=50, description="직원 이름·이메일")] = None,
) -> list[ManagerCandidateResponse]:
    """계약 담당 직원 후보 (A103): 직원 이름·이메일 검색, 같은 이름 → 이름으로 시작 → 나머지
    순으로 20개. 검색어가 없으면 나를 맨 앞에 둔다."""
    term = q.strip() if q and q.strip() else None
    found = await people.manager_candidates(query=term, limit=20, me=user.id)
    return [
        ManagerCandidateResponse(
            employee_id=c.employee_id,
            name=c.name,
            email=c.email,
            department_name=c.department_name,
            team_name=c.team_name,
            position_name=c.position_name,
            is_me=c.is_me,
        )
        for c in found
    ]


@router.post("/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: ContractFields, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    return await _one(await contracts.create(body.model_dump(), actor_id=user.id), people)


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID, _: Reader, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    return await _one(await contracts.get(contract_id), people)


@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: uuid.UUID,
    body: ContractUpdate,
    user: Manager,
    contracts: ContractsDep,
    people: PeopleDep,
) -> ContractResponse:
    changes = body.model_dump(exclude_unset=True)
    # null은 비울 수 있는 필드에만 의미가 있다. 그 밖의 필드에 null을 보내면 바꾸지 않는다
    changes = {k: v for k, v in changes.items() if v is not None or k in _NULLABLE}
    return await _one(await contracts.update(contract_id, changes, actor_id=user.id), people)


@router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep
) -> Response:
    await contracts.delete(contract_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/contracts/{contract_id}/confirm", response_model=ContractResponse)
async def confirm_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    """DRAFT → ACTIVE (계약서 필요). 종료일이 이미 지났으면 ENDED로 확정한다."""
    return await _one(await contracts.confirm(contract_id, actor_id=user.id), people)


@router.post("/contracts/{contract_id}/terminate", response_model=ContractResponse)
async def terminate_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    """ACTIVE → TERMINATED (중도 해지)."""
    return await _one(await contracts.terminate(contract_id, actor_id=user.id), people)


@router.post("/contracts/{contract_id}/link", response_model=ContractResponse)
async def link_contract(
    contract_id: uuid.UUID,
    body: ContractLink,
    user: Manager,
    contracts: ContractsDep,
    people: PeopleDep,
) -> ContractResponse:
    """가입한 멘토·강사 프로필에 수동 연결·변경 (계약 상태와 무관, A27)."""
    if (body.mentor_id is None) == (body.instructor_id is None):
        raise BusinessRuleViolation(
            "mentor_id와 instructor_id 중 하나만 보내야 합니다.", code="invalid_contract_link"
        )
    view = await contracts.link(
        contract_id, mentor_id=body.mentor_id, instructor_id=body.instructor_id, actor_id=user.id
    )
    return await _one(view, people)


@router.delete("/contracts/{contract_id}/link", response_model=ContractResponse)
async def unlink_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    return await _one(await contracts.link(contract_id, actor_id=user.id), people)


@router.get("/contracts/{contract_id}/file-url", response_model=FileUrlResponse)
async def contract_file_url(
    contract_id: uuid.UUID, _: Reader, contracts: ContractsDep
) -> FileUrlResponse:
    """계약서 다운로드 presigned GET URL (만료 10분, 원본 파일 이름으로 저장)."""
    url, file = await contracts.file_url(contract_id)
    return FileUrlResponse(url=url, file=ContractFileResponse.of(file))

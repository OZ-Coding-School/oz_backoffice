"""계약·계약서 관리 API. 권한: educator.contract.read·manage + 담당 범위 (decisions A109⑦).

- 계약서 업로드: POST /contract-files/uploads → 브라우저가 S3로 직접 업로드
  → POST /contract-files/uploads/{upload_id}/confirm
- 계약: 목록·생성·조회·수정(서명 전 전부, 서명 후 담당 직원만)·삭제(초안만)·계약서 URL
- 상태: 진행(`/progress`)·완료(`/sign`)·종료(`/end`)·취소(`/cancel`)·해지(`/terminate`) (A109③)
- 변경 계약: `/amendments` 등록·이력 (A109⑨)
- 응답에 담당 직원·연결된 프로필·과정·기수 이름, 담당 직원 후보 (A103)
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, Field

from app.contexts.access.presentation.dependencies import (
    PermissionCheckerDep,
    require_permission,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.contract_files import ContractFileUploadService
from app.contexts.educator.application.contract_people import (
    ContractPeople,
    ContractPeopleReader,
    LinkedPerson,
)
from app.contexts.educator.application.contracts import (
    AmendmentView,
    ContractService,
    ContractView,
)
from app.contexts.educator.application.ports import AcademyDirectory, EmployeeDirectory
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.enums import (
    ContractStatus,
    ContractType,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    TerminationReason,
    VatType,
)
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.pending_uploads import RedisPendingUploadStore
from app.contexts.educator.infrastructure.repositories import (
    TortoiseContractAmendmentRepository,
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
    checker: PermissionCheckerDep,
) -> ContractService:
    return ContractService(
        contracts=TortoiseEducatorContractRepository(),
        amendments=TortoiseContractAmendmentRepository(),
        files=TortoiseContractFileRepository(),
        mentors=TortoiseMentorRepository(),
        instructors=TortoiseInstructorRepository(),
        employees=cast("EmployeeDirectory", request.app.state.employee_queries),
        academy=cast("AcademyDirectory", request.app.state.academy_catalog),
        storage=storage,
        audit=cast("AuditRecorder", request.app.state.audit_recorder),
        uow=UnitOfWork(),
        clock=clock,
        permissions=checker,
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


class ContractTerms(BaseModel):
    """계약 내용 (A109④⑤). 변경 계약에서도 같은 이름으로 보낸다."""

    title: str = Field(min_length=1, max_length=100, description="계약 명칭")
    contractor_name: str = Field(min_length=1, max_length=50, description="당사자 이름·업체명")
    contractor_phone: str | None = Field(
        default=None, max_length=20, description="멘토·강사는 휴대폰 필수, 그 밖은 일반 번호 가능"
    )
    contractor_email: str | None = Field(default=None, max_length=255)
    business_registration_number: str | None = Field(
        default=None, max_length=20, description="사업자등록번호 10자리 (SW·장비·기타만)"
    )
    contact_person_name: str | None = Field(
        default=None, max_length=50, description="업체 담당자 이름 (SW·장비·기타만)"
    )
    start_date: date | None = None
    end_date: date | None = None
    settlement_type: SettlementType
    total_amount: int | None = Field(
        default=None, ge=0, description="정액: 총액(필수), 단가: 예상 총액, 실비: 한도액"
    )
    unit_price: int | None = Field(default=None, ge=0, description="단가 계약만 필수")
    price_unit: PriceUnit | None = Field(default=None, description="단가 계약만 필수")
    vat_type: VatType = VatType.NOT_APPLICABLE
    amount_note: str | None = Field(default=None, max_length=500)
    no_show_pay_amount: int | None = Field(
        default=None, ge=0, description="멘토 계약만 필수: 노쇼 1건 금액"
    )
    mentoring_time_basis: MentoringTimeBasis | None = Field(
        default=None, description="멘토 계약만 필수: 멘토링 정산 시간 기준"
    )


class ContractFields(ContractTerms):
    contract_type: ContractType
    bootcamp_id: uuid.UUID
    cohort_id: uuid.UUID | None = Field(default=None, description="없으면 과정 공통 계약")
    manager_employee_id: uuid.UUID
    contract_file_id: uuid.UUID | None = None
    mentor_id: uuid.UUID | None = Field(
        default=None,
        description="멘토 계약이 속할 멘토 (A104). 없으면 이름·휴대폰이 같은 멘토, 그것도 없으면"
        " 가입 전 멘토를 만든다",
    )


class ContractUpdate(BaseModel):
    """보낸 필드만 바꾼다. 서명 전(DRAFT·IN_PROGRESS)은 모든 항목, 서명 후는 담당 직원만."""

    contract_type: ContractType | None = None
    bootcamp_id: uuid.UUID | None = None
    cohort_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=100)
    contractor_name: str | None = Field(default=None, min_length=1, max_length=50)
    contractor_phone: str | None = Field(default=None, max_length=20)
    contractor_email: str | None = Field(default=None, max_length=255)
    business_registration_number: str | None = Field(default=None, max_length=20)
    contact_person_name: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    settlement_type: SettlementType | None = None
    total_amount: int | None = Field(default=None, ge=0)
    unit_price: int | None = Field(default=None, ge=0)
    price_unit: PriceUnit | None = None
    vat_type: VatType | None = None
    amount_note: str | None = Field(default=None, max_length=500)
    no_show_pay_amount: int | None = Field(default=None, ge=0)
    mentoring_time_basis: MentoringTimeBasis | None = None
    manager_employee_id: uuid.UUID | None = None
    contract_file_id: uuid.UUID | None = None


# null을 보내면 비우는 필드 (나머지는 null이면 바꾸지 않는다)
_NULLABLE = frozenset(
    {
        "cohort_id",
        "contractor_phone",
        "contractor_email",
        "business_registration_number",
        "contact_person_name",
        "start_date",
        "end_date",
        "total_amount",
        "unit_price",
        "price_unit",
        "amount_note",
        "no_show_pay_amount",
        "mentoring_time_basis",
        "contract_file_id",
    }
)


class AmendmentChanges(BaseModel):
    """변경 계약으로 바꿀 항목 (A109⑨). 보낸 필드만 바꾸고 null은 비운다(필수 칸 제외)."""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    contractor_phone: str | None = Field(default=None, max_length=20)
    contractor_email: str | None = Field(default=None, max_length=255)
    business_registration_number: str | None = Field(default=None, max_length=20)
    contact_person_name: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None
    settlement_type: SettlementType | None = None
    total_amount: int | None = Field(default=None, ge=0)
    unit_price: int | None = Field(default=None, ge=0)
    price_unit: PriceUnit | None = None
    vat_type: VatType | None = None
    amount_note: str | None = Field(default=None, max_length=500)
    no_show_pay_amount: int | None = Field(default=None, ge=0)
    mentoring_time_basis: MentoringTimeBasis | None = None


class AmendmentRequest(BaseModel):
    amended_on: date = Field(description="변경 일자")
    reason: str = Field(min_length=1, max_length=500, description="변경 사유")
    changes: AmendmentChanges
    contract_file_id: uuid.UUID | None = Field(default=None, description="변경 계약서 (선택)")


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500, description="취소 사유")
    canceled_on: date | None = Field(default=None, description="없으면 오늘")


class TerminateRequest(BaseModel):
    reason: TerminationReason
    detail: str | None = Field(default=None, max_length=500, description="해지 사유 상세")
    terminated_on: date | None = Field(default=None, description="없으면 오늘")


class LinkedProfileResponse(BaseModel):
    name: str = Field(description="실명")
    display_name: str = Field(description="수강생에게 보이는 이름")

    @classmethod
    def of(cls, person: LinkedPerson | None) -> "LinkedProfileResponse | None":
        return cls(name=person.name, display_name=person.display_name) if person else None


class ContractResponse(BaseModel):
    id: uuid.UUID
    contract_type: ContractType
    status: ContractStatus
    title: str
    contractor_name: str
    contractor_phone: str | None
    contractor_email: str | None
    business_registration_number: str | None
    contact_person_name: str | None
    start_date: date | None
    end_date: date | None
    settlement_type: SettlementType
    total_amount: int | None
    unit_price: int | None
    price_unit: PriceUnit | None
    vat_type: VatType
    amount_note: str | None
    no_show_pay_amount: int | None
    mentoring_time_basis: MentoringTimeBasis | None
    bootcamp_id: uuid.UUID
    bootcamp_name: str | None = Field(description="과정 이름")
    cohort_id: uuid.UUID | None
    cohort_number: int | None = Field(description="기수 번호 (과정 공통 계약이면 null)")
    manager_employee_id: uuid.UUID
    manager_name: str | None = Field(description="담당 직원 이름 (A103)")
    mentor_id: uuid.UUID | None
    instructor_id: uuid.UUID | None
    linked_profile: LinkedProfileResponse | None = Field(
        description="연결된 멘토·강사 프로필 이름 (A103)"
    )
    contract_file: ContractFileResponse | None
    cancel_reason: str | None
    canceled_on: date | None
    termination_reason: TerminationReason | None
    termination_detail: str | None
    terminated_on: date | None
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
            contract_type=c.contract_type,
            status=c.status,
            bootcamp_id=c.bootcamp_id,
            bootcamp_name=people.bootcamps.get(c.bootcamp_id),
            cohort_id=c.cohort_id,
            cohort_number=people.cohorts.get(c.cohort_id) if c.cohort_id else None,
            title=c.title,
            contractor_name=c.contractor_name,
            contractor_phone=c.contractor_phone,
            contractor_email=c.contractor_email,
            business_registration_number=c.business_registration_number,
            contact_person_name=c.contact_person_name,
            start_date=c.start_date,
            end_date=c.end_date,
            settlement_type=c.settlement_type,
            total_amount=c.total_amount,
            unit_price=c.unit_price,
            price_unit=c.price_unit,
            vat_type=c.vat_type,
            amount_note=c.amount_note,
            no_show_pay_amount=c.no_show_pay_amount,
            mentoring_time_basis=c.mentoring_time_basis,
            manager_employee_id=c.manager_employee_id,
            manager_name=people.managers.get(c.manager_employee_id),
            mentor_id=c.mentor_id,
            instructor_id=c.instructor_id,
            linked_profile=LinkedProfileResponse.of(linked),
            contract_file=ContractFileResponse.of(view.file) if view.file else None,
            cancel_reason=c.cancel_reason,
            canceled_on=c.canceled_on,
            termination_reason=c.termination_reason,
            termination_detail=c.termination_detail,
            terminated_on=c.terminated_on,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )


class AmendmentResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    amended_on: date
    reason: str
    before: dict[str, Any] = Field(description="바뀐 항목의 변경 전 값")
    after: dict[str, Any] = Field(description="바뀐 항목의 변경 후 값")
    contract_file: ContractFileResponse | None
    created_by_user_id: uuid.UUID
    created_by_name: str | None
    created_at: datetime | None

    @classmethod
    def of(cls, view: AmendmentView, names: dict[uuid.UUID, str]) -> "AmendmentResponse":
        a = view.amendment
        return cls(
            id=a.id,
            contract_id=a.contract_id,
            amended_on=a.amended_on,
            reason=a.reason,
            before=a.before,
            after=a.after,
            contract_file=ContractFileResponse.of(view.file) if view.file else None,
            created_by_user_id=a.created_by_user_id,
            created_by_name=names.get(a.created_by_user_id),
            created_at=a.created_at,
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
    user: Reader,
    contracts: ContractsDep,
    people: PeopleDep,
    status_: Annotated[list[ContractStatus] | None, Query(alias="status")] = None,
    contract_type: Annotated[list[ContractType] | None, Query()] = None,
    bootcamp_id: uuid.UUID | None = None,
    cohort_id: uuid.UUID | None = None,
    q: Annotated[
        str | None, Query(max_length=50, description="당사자 이름·계약 명칭·전화번호")
    ] = None,
    mentor_id: Annotated[uuid.UUID | None, Query(description="연결된 멘토 (A103)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ContractResponse]:
    """담당 범위 안의 계약만 (A109⑦). 최근에 만든 계약이 먼저."""
    contract_filter = ContractFilter(
        statuses=frozenset(status_ or ()),
        contract_types=frozenset(contract_type or ()),
        bootcamp_id=bootcamp_id,
        cohort_id=cohort_id,
        query=q.strip() if q and q.strip() else None,
        mentor_id=mentor_id,
    )
    views, total = await contracts.list_contracts(
        contract_filter, actor_id=user.id, limit=limit, offset=offset
    )
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
    values = body.model_dump(exclude={"mentor_id"})
    view = await contracts.create(values, actor_id=user.id, mentor_id=body.mentor_id)
    return await _one(view, people)


@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: uuid.UUID, user: Reader, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    return await _one(await contracts.get(contract_id, actor_id=user.id), people)


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
    """초안(DRAFT)만 지운다."""
    await contracts.delete(contract_id, actor_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/contracts/{contract_id}/progress", response_model=ContractResponse)
async def start_contract_progress(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    """DRAFT → IN_PROGRESS (계약서 필요)."""
    return await _one(await contracts.start_progress(contract_id, actor_id=user.id), people)


@router.post("/contracts/{contract_id}/sign", response_model=ContractResponse)
async def sign_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    """IN_PROGRESS → 계약 완료. 시작일이 없거나 지났으면 ACTIVE, 아니면 SIGNED
    (종료일이 이미 지났으면 ENDED)."""
    return await _one(await contracts.sign(contract_id, actor_id=user.id), people)


@router.post("/contracts/{contract_id}/end", response_model=ContractResponse)
async def end_contract(
    contract_id: uuid.UUID, user: Manager, contracts: ContractsDep, people: PeopleDep
) -> ContractResponse:
    """종료일이 없는 ACTIVE 계약을 끝낸다 (ENDED)."""
    return await _one(await contracts.end(contract_id, actor_id=user.id), people)


@router.post("/contracts/{contract_id}/cancel", response_model=ContractResponse)
async def cancel_contract(
    contract_id: uuid.UUID,
    body: CancelRequest,
    user: Manager,
    contracts: ContractsDep,
    people: PeopleDep,
) -> ContractResponse:
    """DRAFT·IN_PROGRESS → CANCELED (취소 사유 필수)."""
    view = await contracts.cancel(
        contract_id, reason=body.reason, on=body.canceled_on, actor_id=user.id
    )
    return await _one(view, people)


@router.post("/contracts/{contract_id}/terminate", response_model=ContractResponse)
async def terminate_contract(
    contract_id: uuid.UUID,
    body: TerminateRequest,
    user: Manager,
    contracts: ContractsDep,
    people: PeopleDep,
) -> ContractResponse:
    """SIGNED·ACTIVE → TERMINATED (해지 사유·상세·일자)."""
    view = await contracts.terminate(
        contract_id,
        reason=body.reason,
        detail=body.detail,
        on=body.terminated_on,
        actor_id=user.id,
    )
    return await _one(view, people)


@router.post(
    "/contracts/{contract_id}/amendments",
    response_model=AmendmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def amend_contract(
    contract_id: uuid.UUID,
    body: AmendmentRequest,
    user: Manager,
    contracts: ContractsDep,
    people: PeopleDep,
) -> AmendmentResponse:
    """서명 후(SIGNED·ACTIVE) 변경 계약 (A109⑨): 명칭·금액·기간·당사자 연락처."""
    view = await contracts.amend(
        contract_id,
        body.changes.model_dump(exclude_unset=True),
        amended_on=body.amended_on,
        reason=body.reason,
        contract_file_id=body.contract_file_id,
        actor_id=user.id,
    )
    names = await people.user_names([view.amendment.created_by_user_id])
    return AmendmentResponse.of(view, names)


@router.get("/contracts/{contract_id}/amendments", response_model=list[AmendmentResponse])
async def list_contract_amendments(
    contract_id: uuid.UUID, user: Reader, contracts: ContractsDep, people: PeopleDep
) -> list[AmendmentResponse]:
    """변경 이력, 최근 변경이 먼저."""
    views = await contracts.amendments(contract_id, actor_id=user.id)
    names = await people.user_names([v.amendment.created_by_user_id for v in views])
    return [AmendmentResponse.of(v, names) for v in views]


@router.get(
    "/contracts/{contract_id}/amendments/{amendment_id}/file-url",
    response_model=FileUrlResponse,
)
async def amendment_file_url(
    contract_id: uuid.UUID, amendment_id: uuid.UUID, user: Reader, contracts: ContractsDep
) -> FileUrlResponse:
    """변경 계약서 다운로드 presigned GET URL."""
    url, file = await contracts.amendment_file_url(contract_id, amendment_id, actor_id=user.id)
    return FileUrlResponse(url=url, file=ContractFileResponse.of(file))


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
    contract_id: uuid.UUID, user: Reader, contracts: ContractsDep
) -> FileUrlResponse:
    """계약서 다운로드 presigned GET URL (만료 10분, 원본 파일 이름으로 저장)."""
    url, file = await contracts.file_url(contract_id, actor_id=user.id)
    return FileUrlResponse(url=url, file=ContractFileResponse.of(file))

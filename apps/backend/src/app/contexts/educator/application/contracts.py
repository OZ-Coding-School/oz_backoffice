"""계약 관리 (권한 educator.contract.read·manage, decisions A109, 이전 A23~A27·A104).

- 생성은 항상 DRAFT. 담당 직원은 항상 입력받고 존재하는지 확인한다.
- 과정은 필수, 기수는 그 과정의 기수만(없으면 과정 공통 계약). 범위는 담당 범위를 따른다(A109⑦):
  조회 범위 밖이면 404, 조회는 되지만 관리 범위 밖이면 403.
- 서명 전(DRAFT·IN_PROGRESS)은 그냥 고치고, 서명 후(SIGNED·ACTIVE)는 변경 계약으로만 바꾼다.
  담당 직원은 언제나 바로 바꾼다. 삭제는 DRAFT만.
- 계약서는 확정된 업로드(contract_files)만 붙일 수 있고, 다른 계약·변경 계약이 쓰는 파일은 붙일 수
  없다. 교체하거나 비우거나 계약을 지우면 이전 파일은 deleted_at만 채우고 객체는 남긴다(A25).
- 멘토 계약은 항상 멘토에 속한다(A104): 만들 때 지정한 멘토, 없으면 이름·휴대폰이 같은 멘토
  하나, 그것도 없으면 가입 전 멘토를 만든다. 연결 해제는 없고 다른 멘토로 옮길 수만 있다.
  가입 전 멘토의 마지막 계약을 지우거나 옮기면 그 멘토도 지운다.
- 기수 배정의 근거 계약(A110): 계약이 ENDED·TERMINATED가 되거나 기간이 바뀌면 listener가 같은
  트랜잭션에서 배정을 정리한다. 활성 배정의 근거인 계약은 다른 멘토로 옮길 수 없다(409).
모든 변경은 감사 로그를 남긴다. 날짜에 따른 자동 처리의 행위자는 시스템(None)이다.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from app.contexts.access.application.permissions import PermissionTarget
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.ports import (
    AcademyDirectory,
    ContractLifecycleListener,
    ContractPermissions,
    EmployeeDirectory,
    FileStorage,
)
from app.contexts.educator.domain.entities import (
    ContractAmendment,
    ContractFile,
    EducatorContract,
)
from app.contexts.educator.domain.enums import ContractStatus, ContractType, TerminationReason
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import (
    ContractAmendmentRepository,
    ContractFileRepository,
    ContractFilter,
    ContractVisibility,
    EducatorContractRepository,
    InstructorRepository,
    MentorRepository,
)
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.shared.time import business_date

TARGET = "educator_contract"
CLOSED = frozenset({ContractStatus.ENDED, ContractStatus.TERMINATED})
READ = "educator.contract.read"
MANAGE = "educator.contract.manage"


@dataclass(frozen=True, slots=True)
class ContractView:
    contract: EducatorContract
    file: ContractFile | None
    signed_file: ContractFile | None = None


@dataclass(frozen=True, slots=True)
class ContractList:
    views: list[ContractView]
    total: int
    counts: dict[ContractType, int]


@dataclass(frozen=True, slots=True)
class AmendmentView:
    amendment: ContractAmendment
    file: ContractFile | None


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _snapshot(contract: EducatorContract) -> dict[str, Any]:
    skip = {"id", "created_at", "updated_at"}
    return {
        f.name: _jsonable(getattr(contract, f.name))
        for f in dataclasses.fields(contract)
        if f.init and f.name not in skip
    }


def _target(contract: EducatorContract) -> PermissionTarget:
    """기수 계약은 기수(과정 담당도 포함), 과정 공통 계약은 과정으로 판정한다."""
    if contract.cohort_id is not None:
        return PermissionTarget.cohort(contract.cohort_id)
    return PermissionTarget.bootcamp(contract.bootcamp_id)


def _not_found() -> NotFoundError:
    return NotFoundError("계약을 찾을 수 없습니다.", code="contract_not_found")


class ContractService:
    def __init__(
        self,
        *,
        contracts: EducatorContractRepository,
        amendments: ContractAmendmentRepository,
        files: ContractFileRepository,
        mentors: MentorRepository,
        instructors: InstructorRepository,
        employees: EmployeeDirectory,
        academy: AcademyDirectory,
        storage: FileStorage,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        permissions: ContractPermissions | None = None,
        listener: ContractLifecycleListener | None = None,
    ) -> None:
        """permissions가 없으면(매일 작업) 범위 검사를 하지 않는다."""
        self._contracts = contracts
        self._amendments = amendments
        self._files = files
        self._mentors = mentors
        self._instructors = instructors
        self._employees = employees
        self._academy = academy
        self._storage = storage
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._permissions = permissions
        self._listener = listener

    # ------------------------------------------------------------------ 조회
    async def list_contracts(
        self,
        contract_filter: ContractFilter,
        *,
        actor_id: uuid.UUID,
        limit: int,
        offset: int,
        include_bootcamp_common: bool = False,
    ) -> ContractList:
        """담당 범위 안의 계약과 종류별 건수 (A109⑦·A112).

        `include_bootcamp_common`이면 기수 필터에 그 기수가 속한 과정의 과정 공통 계약을 더한다.
        """
        visible = await self._visibility(actor_id)
        contract_filter = dataclasses.replace(contract_filter, visible=visible)
        if include_bootcamp_common and contract_filter.cohort_id is not None:
            bootcamp_id = await self._academy.bootcamp_id_of(contract_filter.cohort_id)
            contract_filter = dataclasses.replace(contract_filter, common_bootcamp_id=bootcamp_id)
        contracts, total = await self._contracts.list_page(
            contract_filter, limit=limit, offset=offset
        )
        counts = await self._contracts.count_by_types(contract_filter)
        file_ids = [
            f for c in contracts for f in (c.contract_file_id, c.signed_contract_file_id) if f
        ]
        files = {f.id: f for f in await self._files.list_by_ids(file_ids)}
        views = [
            ContractView(
                c,
                files.get(c.contract_file_id) if c.contract_file_id else None,
                files.get(c.signed_contract_file_id) if c.signed_contract_file_id else None,
            )
            for c in contracts
        ]
        return ContractList(views=views, total=total, counts=counts)

    async def get(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractView:
        contract = await self._readable(contract_id, actor_id)
        return ContractView(
            contract,
            await self._file_of(contract.contract_file_id),
            await self._file_of(contract.signed_contract_file_id),
        )

    async def file_url(
        self, contract_id: uuid.UUID, *, actor_id: uuid.UUID, signed: bool = False
    ) -> tuple[str, ContractFile]:
        """계약서(원본 또는 서명본, A113) 다운로드 presigned GET URL (원본 파일 이름으로 저장)."""
        contract = await self._readable(contract_id, actor_id)
        file = await self._file_of(
            contract.signed_contract_file_id if signed else contract.contract_file_id
        )
        if file is None:
            raise NotFoundError("계약서가 없습니다.", code="contract_file_not_found")
        url = await self._storage.presign_get(file.storage_key, download_name=file.file_name)
        return url, file

    async def amendments(
        self, contract_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> list[AmendmentView]:
        await self._readable(contract_id, actor_id)
        found = await self._amendments.list_by_contract(contract_id)
        files = {
            f.id: f
            for f in await self._files.list_by_ids(
                [a.contract_file_id for a in found if a.contract_file_id]
            )
        }
        return [
            AmendmentView(a, files.get(a.contract_file_id) if a.contract_file_id else None)
            for a in found
        ]

    async def amendment_file_url(
        self, contract_id: uuid.UUID, amendment_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> tuple[str, ContractFile]:
        await self._readable(contract_id, actor_id)
        amendment = next(
            (
                a
                for a in await self._amendments.list_by_contract(contract_id)
                if a.id == amendment_id
            ),
            None,
        )
        file = await self._file_of(amendment.contract_file_id if amendment else None)
        if file is None:
            raise NotFoundError("계약서가 없습니다.", code="contract_file_not_found")
        url = await self._storage.presign_get(file.storage_key, download_name=file.file_name)
        return url, file

    # ------------------------------------------------------------------ 변경
    async def create(
        self,
        values: dict[str, Any],
        *,
        actor_id: uuid.UUID,
        mentor_id: uuid.UUID | None = None,
    ) -> ContractView:
        contract = EducatorContract(**values)
        async with self._uow:
            await self._ensure_belongs(contract)
            await self._require_manage(contract, actor_id)
            await self._ensure_employee(contract.manager_employee_id)
            file = await self._attachable_file(contract.contract_file_id)
            if contract.contract_type is ContractType.MENTOR:
                mentor = await self._mentor_for(contract, mentor_id, actor_id=actor_id)
                contract.link(mentor_id=mentor.id, instructor_id=None)
            elif mentor_id is not None:
                raise BusinessRuleViolation(
                    "계약 종류와 연결할 프로필 종류가 다릅니다.", code="contract_type_mismatch"
                )
            await self._contracts.add(contract)
            await self._record(actor_id, "create", contract)
        return ContractView(await self._get(contract.id), file)

    async def update(
        self, contract_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> ContractView:
        async with self._uow:
            current = await self._manageable(contract_id, actor_id)
            updated = current.revised(changes)
            linked = current.mentor_id is not None or current.instructor_id is not None
            if linked and updated.contract_type is not current.contract_type:
                raise BusinessRuleViolation(
                    "멘토·강사에 속한 계약은 종류를 바꿀 수 없습니다.",
                    code="contract_type_mismatch",
                )
            if (updated.bootcamp_id, updated.cohort_id) != (current.bootcamp_id, current.cohort_id):
                await self._ensure_belongs(updated)
                await self._require_manage(updated, actor_id)
            await self._sync_pending_contact(updated)
            if updated.manager_employee_id != current.manager_employee_id:
                await self._ensure_employee(updated.manager_employee_id)
            if updated.contract_file_id != current.contract_file_id:
                await self._attachable_file(updated.contract_file_id, exclude=current.id)
                await self._discard_file(current.contract_file_id)
            await self._contracts.save(updated)
            await self._record(actor_id, "update", updated, before=current)
        return await self.get(contract_id, actor_id=actor_id)

    async def amend(
        self,
        contract_id: uuid.UUID,
        changes: dict[str, Any],
        *,
        amended_on: date,
        reason: str,
        contract_file_id: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> AmendmentView:
        """서명 후 변경 계약 (A109⑨): 바뀐 항목의 전·후 값을 남기고 계약에 최신 값을 반영한다."""
        async with self._uow:
            current = await self._manageable(contract_id, actor_id)
            changed = {k: v for k, v in changes.items() if getattr(current, k, object()) != v}
            updated = current.amended(changed)
            # 정규화(휴대폰 숫자만 등) 뒤에도 같으면 바뀐 것이 아니다
            fields = [k for k in changed if getattr(updated, k) != getattr(current, k)]
            if not fields:
                raise BusinessRuleViolation("바꿀 항목이 없습니다.", code="amendment_no_changes")
            file = await self._attachable_file(contract_file_id)
            amendment = ContractAmendment(
                contract_id=current.id,
                amended_on=amended_on,
                reason=reason,
                before={k: _jsonable(getattr(current, k)) for k in fields},
                after={k: _jsonable(getattr(updated, k)) for k in fields},
                created_by_user_id=actor_id,
                contract_file_id=contract_file_id,
            )
            updated.advance(today=business_date(self._clock.now()))
            await self._sync_pending_contact(updated)
            await self._contracts.save(updated)
            await self._amendments.add(amendment)
            await self._record(actor_id, "amend", updated, before=current)
            await self._notify(current, updated, actor_id)
        return AmendmentView(amendment, file)

    async def start_progress(
        self,
        contract_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        contract_file_id: uuid.UUID | None = None,
    ) -> ContractView:
        """계약 진행. 계약서 원본(미서명)을 함께 주면 붙이고 이전 파일은 지운다 (A113)."""
        async with self._uow:
            contract = await self._manageable(contract_id, actor_id)
            before = dataclasses.replace(contract)
            if contract_file_id is not None and contract_file_id != contract.contract_file_id:
                await self._attachable_file(contract_file_id, exclude=contract.id)
                await self._discard_file(contract.contract_file_id)
            contract.start_progress(contract_file_id=contract_file_id)
            await self._contracts.save(contract)
            await self._record(actor_id, "start", contract, before=before)
        return await self.get(contract_id, actor_id=actor_id)

    async def sign(
        self, contract_id: uuid.UUID, *, actor_id: uuid.UUID, signed_contract_file_id: uuid.UUID
    ) -> ContractView:
        """계약 완료. 서명된 계약서를 함께 받는다 (A113)."""
        today = business_date(self._clock.now())
        async with self._uow:
            contract = await self._manageable(contract_id, actor_id)
            before = dataclasses.replace(contract)
            if signed_contract_file_id != contract.contract_file_id:
                await self._attachable_file(signed_contract_file_id, exclude=contract.id)
            contract.sign(today=today, signed_contract_file_id=signed_contract_file_id)
            await self._contracts.save(contract)
            await self._record(actor_id, "sign", contract, before=before)
            await self._notify(before, contract, actor_id)
        return await self.get(contract_id, actor_id=actor_id)

    async def end(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractView:
        return await self._transition(contract_id, "end", actor_id, lambda c: c.end())

    async def cancel(
        self, contract_id: uuid.UUID, *, reason: str, on: date | None, actor_id: uuid.UUID
    ) -> ContractView:
        day = on or business_date(self._clock.now())
        return await self._transition(
            contract_id, "cancel", actor_id, lambda c: c.cancel(reason=reason, on=day)
        )

    async def terminate(
        self,
        contract_id: uuid.UUID,
        *,
        reason: TerminationReason,
        detail: str | None,
        on: date | None,
        actor_id: uuid.UUID,
    ) -> ContractView:
        day = on or business_date(self._clock.now())
        return await self._transition(
            contract_id,
            "terminate",
            actor_id,
            lambda c: c.terminate(reason=reason, detail=detail, on=day),
        )

    async def link(
        self,
        contract_id: uuid.UUID,
        *,
        mentor_id: uuid.UUID | None = None,
        instructor_id: uuid.UUID | None = None,
        actor_id: uuid.UUID,
    ) -> ContractView:
        """가입한 멘토·강사 프로필에 수동 연결·변경한다. 둘 다 None이면 해제(A27)."""
        async with self._uow:
            contract = await self._manageable(contract_id, actor_id)
            before = dataclasses.replace(contract)
            contract.link(mentor_id=mentor_id, instructor_id=instructor_id)
            moved = before.mentor_id is not None and before.mentor_id != contract.mentor_id
            if (
                moved
                and self._listener
                and await self._listener.has_active_assignments(contract.id)
            ):
                raise ConflictError(
                    "기수 배정의 근거인 계약은 다른 멘토로 옮길 수 없습니다. "
                    "배정을 먼저 끝내 주세요.",
                    code="contract_in_use_by_assignment",
                )
            if mentor_id is not None and await self._mentors.get(mentor_id) is None:
                raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
            if instructor_id is not None and not await self._instructors.exists(instructor_id):
                raise NotFoundError("강사를 찾을 수 없습니다.", code="instructor_not_found")
            await self._contracts.save(contract)
            action = "unlink" if mentor_id is None and instructor_id is None else "link"
            await self._record(actor_id, action, contract, before=before)
            if before.mentor_id is not None and before.mentor_id != contract.mentor_id:
                await self._drop_empty_pending(before.mentor_id, actor_id=actor_id)
        return await self.get(contract_id, actor_id=actor_id)

    async def delete(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            current = await self._manageable(contract_id, actor_id)
            current.ensure_deletable()
            await self._contracts.delete(contract_id)
            await self._discard_file(current.contract_file_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="educator.contract.delete",
                target_type=TARGET,
                target_id=contract_id,
                before=_snapshot(current),
            )
            if current.mentor_id is not None:
                await self._drop_empty_pending(current.mentor_id, actor_id=actor_id)

    async def advance_due(self) -> int:
        """시작일이 된 SIGNED → ACTIVE, 종료일이 지난 ACTIVE → ENDED (매일 작업, 멱등).
        바꾼 건수를 돌려준다."""
        today = business_date(self._clock.now())
        changed = 0
        async with self._uow:
            for contract in await self._contracts.list_due(today):
                before = dataclasses.replace(contract)
                if contract.advance(today=today):
                    await self._contracts.save(contract)
                    await self._record(None, "advance", contract, before=before)
                    await self._notify(before, contract, None)
                    changed += 1
        return changed

    # ------------------------------------------------------------------ 범위
    async def _visibility(self, actor_id: uuid.UUID) -> ContractVisibility | None:
        if self._permissions is None:
            return None
        scope = await self._permissions.scope_of(actor_id, READ)
        if scope.is_global:
            return None
        return ContractVisibility(bootcamp_ids=scope.bootcamp_ids, cohort_ids=scope.cohort_ids)

    async def _readable(self, contract_id: uuid.UUID, actor_id: uuid.UUID) -> EducatorContract:
        contract = await self._get(contract_id)
        if self._permissions is not None and not await self._permissions.has(
            actor_id, READ, _target(contract)
        ):
            raise _not_found()
        return contract

    async def _manageable(self, contract_id: uuid.UUID, actor_id: uuid.UUID) -> EducatorContract:
        contract = await self._readable(contract_id, actor_id)
        await self._require_manage(contract, actor_id)
        return contract

    async def _require_manage(self, contract: EducatorContract, actor_id: uuid.UUID) -> None:
        if self._permissions is not None and not await self._permissions.has(
            actor_id, MANAGE, _target(contract)
        ):
            raise PermissionDeniedError(
                "이 과정·기수의 계약을 관리할 권한이 없습니다.", code="permission_denied"
            )

    async def _ensure_belongs(self, contract: EducatorContract) -> None:
        """과정이 있어야 하고, 기수는 그 과정의 기수여야 한다 (A109②)."""
        if not await self._academy.bootcamp_names([contract.bootcamp_id]):
            raise NotFoundError("과정을 찾을 수 없습니다.", code="bootcamp_not_found")
        if contract.cohort_id is None:
            return
        owner = await self._academy.bootcamp_id_of(contract.cohort_id)
        if owner is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")
        if owner != contract.bootcamp_id:
            raise BusinessRuleViolation(
                "기수가 계약의 과정에 속하지 않습니다.", code="cohort_not_in_bootcamp"
            )

    # ------------------------------------------------------------------ 내부
    async def _mentor_for(
        self, contract: EducatorContract, mentor_id: uuid.UUID | None, *, actor_id: uuid.UUID
    ) -> Mentor:
        """계약이 속할 멘토 (A104): 지정한 멘토 → 같은 사람 하나 → 새 가입 전 멘토."""
        if mentor_id is not None:
            mentor = await self._mentors.get(mentor_id)
            if mentor is None:
                raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
            return mentor
        phone = contract.contractor_phone or ""
        same = await self._mentors.find_same_person(contract.contractor_name, phone)
        if len(same) > 1:
            raise ConflictError(
                "이름과 휴대폰이 같은 멘토가 여럿이에요. 멘토 상세에서 계약을 추가해 주세요.",
                code="ambiguous_mentor",
            )
        if same:
            return same[0]
        mentor = Mentor.pending(name=contract.contractor_name, phone=phone)
        await self._mentors.add(mentor)
        await self._audit.record(
            actor_user_id=actor_id,
            action="educator.mentor.create_pending",
            target_type="mentor",
            target_id=mentor.id,
            after={"contact_name": mentor.contact_name},
        )
        return mentor

    async def _sync_pending_contact(self, contract: EducatorContract) -> None:
        """가입 전 멘토의 연락처를 고친 계약자 정보에 맞춘다."""
        if contract.mentor_id is None or contract.contractor_phone is None:
            return
        mentor = await self._mentors.get(contract.mentor_id)
        if mentor is not None and not mentor.is_registered:
            mentor.update_contact(name=contract.contractor_name, phone=contract.contractor_phone)
            await self._mentors.save(mentor)

    async def _drop_empty_pending(self, mentor_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """계약이 하나도 남지 않은 가입 전 멘토는 지운다 (A104)."""
        mentor = await self._mentors.get(mentor_id)
        if mentor is None or mentor.is_registered:
            return
        if (await self._contracts.count_by_mentors([mentor_id])).get(mentor_id, 0) > 0:
            return
        await self._mentors.delete(mentor_id)
        await self._audit.record(
            actor_user_id=actor_id,
            action="educator.mentor.delete_pending",
            target_type="mentor",
            target_id=mentor_id,
            before={"contact_name": mentor.contact_name},
        )

    async def _transition(
        self, contract_id: uuid.UUID, action: str, actor_id: uuid.UUID, change: Any
    ) -> ContractView:
        async with self._uow:
            contract = await self._manageable(contract_id, actor_id)
            before = dataclasses.replace(contract)
            change(contract)
            await self._contracts.save(contract)
            await self._record(actor_id, action, contract, before=before)
            await self._notify(before, contract, actor_id)
        return await self.get(contract_id, actor_id=actor_id)

    async def _notify(
        self, before: EducatorContract, after: EducatorContract, actor_id: uuid.UUID | None
    ) -> None:
        """멘토 계약이 끝나거나 기간이 바뀌면 기수 배정을 정리한다 (A110)."""
        if self._listener is None or after.contract_type is not ContractType.MENTOR:
            return
        if after.status in CLOSED and before.status not in CLOSED:
            await self._listener.contract_closed(after.id, actor_id=actor_id)
        elif (before.start_date, before.end_date) != (after.start_date, after.end_date):
            await self._listener.contract_period_changed(
                after.id, start_date=after.start_date, end_date=after.end_date, actor_id=actor_id
            )

    async def _get(self, contract_id: uuid.UUID) -> EducatorContract:
        contract = await self._contracts.get(contract_id)
        if contract is None:
            raise _not_found()
        return contract

    async def _file_of(self, file_id: uuid.UUID | None) -> ContractFile | None:
        if file_id is None:
            return None
        return await self._files.get(file_id)

    async def _ensure_employee(self, employee_id: uuid.UUID) -> None:
        if not await self._employees.exists(employee_id):
            raise NotFoundError("담당 직원을 찾을 수 없습니다.", code="employee_not_found")

    async def _attachable_file(
        self, file_id: uuid.UUID | None, *, exclude: uuid.UUID | None = None
    ) -> ContractFile | None:
        if file_id is None:
            return None
        file = await self._files.get(file_id)
        if file is None or file.deleted_at is not None:
            raise NotFoundError("계약서 파일을 찾을 수 없습니다.", code="contract_file_not_found")
        owner = await self._contracts.get_by_file(file_id)
        if (owner is not None and owner.id != exclude) or await self._amendments.file_in_use(
            file_id
        ):
            raise ConflictError("다른 계약에 연결된 계약서입니다.", code="contract_file_in_use")
        return file

    async def _discard_file(self, file_id: uuid.UUID | None) -> None:
        if file_id is None:
            return
        file = await self._files.get(file_id)
        if file is not None:
            file.discard(now=self._clock.now())
            await self._files.save(file)

    async def _record(
        self,
        actor_id: uuid.UUID | None,
        action: str,
        contract: EducatorContract,
        *,
        before: EducatorContract | None = None,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"educator.contract.{action}",
            target_type=TARGET,
            target_id=contract.id,
            before=_snapshot(before) if before else None,
            after=_snapshot(contract),
        )

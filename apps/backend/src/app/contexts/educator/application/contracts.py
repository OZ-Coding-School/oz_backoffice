"""교육 인력 계약 관리 (권한 contract.manage, decisions M14·A23·A24·A25).

- 생성은 항상 DRAFT. 담당 직원은 항상 입력받고 존재하는지 확인한다.
- 수정·삭제는 DRAFT일 때만 한다. 확정 후에는 담당 직원만 바꿀 수 있다(엔티티 `revised`).
- 계약서는 확정된 업로드(contract_files)만 붙일 수 있고, 다른 계약이 쓰는 파일은 붙일 수 없다.
  교체하거나 비우거나 계약을 지우면 이전 파일은 deleted_at만 채우고 객체는 남긴다(A25).
- 확정(DRAFT → ACTIVE, 지난 계약은 ENDED), 해지(ACTIVE → TERMINATED), 기간 만료 자동 처리.
- 멘토 계약은 항상 멘토에 속한다(A104): 만들 때 지정한 멘토, 없으면 이름·휴대폰이 같은 멘토
  하나, 그것도 없으면 가입 전 멘토를 만든다. 연결 해제는 없고 다른 멘토로 옮길 수만 있다.
  가입 전 멘토의 마지막 계약을 지우거나 옮기면 그 멘토도 지운다.
모든 변경은 감사 로그를 남긴다. 기간 만료 자동 처리의 행위자는 시스템(None)이다.
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.ports import EmployeeDirectory, FileStorage
from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import EducatorType
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import (
    ContractFileRepository,
    ContractFilter,
    EducatorContractRepository,
    InstructorRepository,
    MentorRepository,
)
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.time import business_date

TARGET = "educator_contract"


@dataclass(frozen=True, slots=True)
class ContractView:
    contract: EducatorContract
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


class ContractService:
    def __init__(
        self,
        *,
        contracts: EducatorContractRepository,
        files: ContractFileRepository,
        mentors: MentorRepository,
        instructors: InstructorRepository,
        employees: EmployeeDirectory,
        storage: FileStorage,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._contracts = contracts
        self._files = files
        self._mentors = mentors
        self._instructors = instructors
        self._employees = employees
        self._storage = storage
        self._audit = audit
        self._uow = uow
        self._clock = clock

    # ------------------------------------------------------------------ 조회
    async def list_contracts(
        self, contract_filter: ContractFilter, *, limit: int, offset: int
    ) -> tuple[list[ContractView], int]:
        contracts, total = await self._contracts.list_page(
            contract_filter, limit=limit, offset=offset
        )
        file_ids = [c.contract_file_id for c in contracts if c.contract_file_id]
        files = {f.id: f for f in await self._files.list_by_ids(file_ids)}
        views = [
            ContractView(c, files.get(c.contract_file_id) if c.contract_file_id else None)
            for c in contracts
        ]
        return views, total

    async def get(self, contract_id: uuid.UUID) -> ContractView:
        contract = await self._get(contract_id)
        return ContractView(contract, await self._file_of(contract))

    async def file_url(self, contract_id: uuid.UUID) -> tuple[str, ContractFile]:
        """계약서 다운로드 presigned GET URL (원본 파일 이름으로 저장)."""
        file = await self._file_of(await self._get(contract_id))
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
            await self._ensure_employee(contract.manager_employee_id)
            file = await self._attachable_file(contract.contract_file_id)
            if contract.educator_type is EducatorType.MENTOR:
                mentor = await self._mentor_for(contract, mentor_id, actor_id=actor_id)
                contract.link(mentor_id=mentor.id, instructor_id=None)
            elif mentor_id is not None:
                raise BusinessRuleViolation(
                    "계약 유형과 연결할 프로필 종류가 다릅니다.", code="contract_type_mismatch"
                )
            await self._contracts.add(contract)
            await self._record(actor_id, "create", contract)
        return ContractView(await self._get(contract.id), file)

    async def update(
        self, contract_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> ContractView:
        async with self._uow:
            current = await self._get(contract_id)
            updated = current.revised(changes)
            linked = current.mentor_id is not None or current.instructor_id is not None
            if linked and updated.educator_type is not current.educator_type:
                raise BusinessRuleViolation(
                    "멘토·강사에 속한 계약은 유형을 바꿀 수 없습니다.",
                    code="contract_type_mismatch",
                )
            await self._sync_pending_contact(updated)
            if updated.manager_employee_id != current.manager_employee_id:
                await self._ensure_employee(updated.manager_employee_id)
            if updated.contract_file_id != current.contract_file_id:
                await self._attachable_file(updated.contract_file_id, exclude=current.id)
                await self._discard_file(current.contract_file_id)
            await self._contracts.save(updated)
            await self._record(actor_id, "update", updated, before=current)
        return await self.get(contract_id)

    async def confirm(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractView:
        return await self._transition(contract_id, "confirm", actor_id=actor_id)

    async def terminate(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractView:
        return await self._transition(contract_id, "terminate", actor_id=actor_id)

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
            contract = await self._get(contract_id)
            before = dataclasses.replace(contract)
            contract.link(mentor_id=mentor_id, instructor_id=instructor_id)
            if mentor_id is not None and await self._mentors.get(mentor_id) is None:
                raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
            if instructor_id is not None and not await self._instructors.exists(instructor_id):
                raise NotFoundError("강사를 찾을 수 없습니다.", code="instructor_not_found")
            await self._contracts.save(contract)
            action = "unlink" if mentor_id is None and instructor_id is None else "link"
            await self._record(actor_id, action, contract, before=before)
            if before.mentor_id is not None and before.mentor_id != contract.mentor_id:
                await self._drop_empty_pending(before.mentor_id, actor_id=actor_id)
        return await self.get(contract_id)

    async def delete(self, contract_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            current = await self._get(contract_id)
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

    async def expire_ended(self) -> int:
        """종료일이 지난 ACTIVE 계약을 ENDED로 바꾼다(매일 작업, 멱등). 바꾼 건수를 돌려준다."""
        today = business_date(self._clock.now())
        async with self._uow:
            contracts = await self._contracts.list_active_ended_before(today)
            for contract in contracts:
                before = dataclasses.replace(contract)
                if contract.expire(today=today):
                    await self._contracts.save(contract)
                    await self._record(None, "expire", contract, before=before)
        return len(contracts)

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
        same = await self._mentors.find_same_person(
            contract.contractor_name, contract.contractor_phone
        )
        if len(same) > 1:
            raise ConflictError(
                "이름과 휴대폰이 같은 멘토가 여럿이에요. 멘토 상세에서 계약을 추가해 주세요.",
                code="ambiguous_mentor",
            )
        if same:
            return same[0]
        mentor = Mentor.pending(name=contract.contractor_name, phone=contract.contractor_phone)
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
        if contract.mentor_id is None:
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
        self, contract_id: uuid.UUID, action: str, *, actor_id: uuid.UUID
    ) -> ContractView:
        async with self._uow:
            contract = await self._get(contract_id)
            before = dataclasses.replace(contract)
            if action == "confirm":
                contract.confirm(today=business_date(self._clock.now()))
            else:
                contract.terminate()
            await self._contracts.save(contract)
            await self._record(actor_id, action, contract, before=before)
        return await self.get(contract_id)

    async def _get(self, contract_id: uuid.UUID) -> EducatorContract:
        contract = await self._contracts.get(contract_id)
        if contract is None:
            raise NotFoundError("계약을 찾을 수 없습니다.", code="contract_not_found")
        return contract

    async def _file_of(self, contract: EducatorContract) -> ContractFile | None:
        if contract.contract_file_id is None:
            return None
        return await self._files.get(contract.contract_file_id)

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
        if owner is not None and owner.id != exclude:
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

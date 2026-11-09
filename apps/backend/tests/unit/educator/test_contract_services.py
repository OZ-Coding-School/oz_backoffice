import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.contract_files import (
    CONTRACT_MAX_BYTES,
    ContractFileUploadService,
)
from app.contexts.educator.application.contracts import ContractService
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.pending_uploads import RedisPendingUploadStore
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import (
    FakeEmployeeDirectory,
    FakeFileStorage,
    InMemoryContractFileRepository,
    InMemoryContractRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

# 2026-11-09 10:00 KST
NOW = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)
PDF = b"%PDF-1.7\n" + b"0" * 100


class Harness:
    def __init__(self, redis: FakeAsyncRedis) -> None:
        self.clock = FixedClock(NOW)
        self.storage = FakeFileStorage()
        self.files = InMemoryContractFileRepository()
        self.contracts = InMemoryContractRepository()
        self.audit_logs = InMemoryAuditLogRepository()
        self.manager_id = new_id()
        self.actor_id = new_id()
        self.employees = FakeEmployeeDirectory(self.manager_id)
        audit = AuditRecorder(self.audit_logs, self.clock)
        self.uploads = ContractFileUploadService(
            uploads=DirectUploads(
                storage=self.storage, pending=RedisPendingUploadStore(redis), clock=self.clock
            ),
            files=self.files,
            audit=audit,
            uow=FakeUnitOfWork(),
        )
        self.service = ContractService(
            contracts=self.contracts,
            files=self.files,
            employees=self.employees,
            storage=self.storage,
            audit=audit,
            uow=FakeUnitOfWork(),
            clock=self.clock,
        )

    async def uploaded_file(self, body: bytes = PDF) -> ContractFile:
        ticket = await self.uploads.request_upload("계약서.pdf", actor_id=self.actor_id)
        self.storage.upload(ticket.fields["key"], body)
        return await self.uploads.confirm(ticket.upload_id, actor_id=self.actor_id)

    def values(self, **overrides: Any) -> dict[str, Any]:
        values: dict[str, Any] = {
            "manager_employee_id": self.manager_id,
            "educator_type": EducatorType.MENTOR,
            "contractor_name": "김멘토",
            "contractor_phone": "01012345678",
            "title": "2026 멘토 계약",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
        }
        values.update(overrides)
        return values

    def actions(self) -> list[str]:
        return [log.action for log in self.audit_logs.logs]


@pytest.fixture
def h(fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(fake_redis)


# ---------------------------------------------------------------- 업로드
async def test_upload_request_and_confirm(h: Harness) -> None:
    ticket = await h.uploads.request_upload("계약서.pdf", actor_id=h.actor_id)
    key = ticket.fields["key"]
    assert key.startswith("contracts/")
    assert key.endswith(".pdf")
    assert ticket.max_bytes == CONTRACT_MAX_BYTES
    h.storage.upload(key, PDF)

    file = await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)

    assert (file.file_name, file.file_ext, file.file_size, file.storage_key) == (
        "계약서.pdf",
        "pdf",
        len(PDF),
        key,
    )
    assert h.actions() == ["educator.contract_file.upload"]
    with pytest.raises(NotFoundError) as again:  # 한 번만 확정
        await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)
    assert again.value.code == "upload_not_found"


async def test_only_requester_can_confirm(h: Harness) -> None:
    ticket = await h.uploads.request_upload("계약서.pdf", actor_id=h.actor_id)
    h.storage.upload(ticket.fields["key"], PDF)

    with pytest.raises(NotFoundError):
        await h.uploads.confirm(ticket.upload_id, actor_id=new_id())
    # 다른 사람의 시도로 요청자의 업로드가 사라지지 않는다
    assert (await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)).file_size == len(PDF)


async def test_confirm_before_upload_can_retry(h: Harness) -> None:
    ticket = await h.uploads.request_upload("계약서.pdf", actor_id=h.actor_id)

    with pytest.raises(BusinessRuleViolation) as exc:
        await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)
    assert exc.value.code == "upload_not_completed"

    h.storage.upload(ticket.fields["key"], PDF)
    assert (await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)).id


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"MZ\x90\x00" + b"0" * 100, "application/pdf"),  # PDF가 아닌 내용
        (PDF, "image/png"),  # 타입 불일치
        (b"%PDF-" + b"0" * CONTRACT_MAX_BYTES, "application/pdf"),  # 크기 초과
    ],
)
async def test_invalid_upload_is_deleted(h: Harness, body: bytes, content_type: str) -> None:
    ticket = await h.uploads.request_upload("계약서.pdf", actor_id=h.actor_id)
    key = ticket.fields["key"]
    h.storage.upload(key, body, content_type)

    with pytest.raises(BusinessRuleViolation) as exc:
        await h.uploads.confirm(ticket.upload_id, actor_id=h.actor_id)

    assert exc.value.code == "invalid_contract_file"
    assert h.storage.deleted == [key]
    assert h.files.items == {}


# ---------------------------------------------------------------- 계약
async def test_create_draft_without_file_then_attach_and_confirm(h: Harness) -> None:
    created = await h.service.create(h.values(), actor_id=h.actor_id)
    assert (created.contract.status, created.file) == (ContractStatus.DRAFT, None)

    file = await h.uploaded_file()
    updated = await h.service.update(
        created.contract.id, {"contract_file_id": file.id}, actor_id=h.actor_id
    )
    assert updated.file is not None
    assert updated.file.id == file.id

    confirmed = await h.service.confirm(created.contract.id, actor_id=h.actor_id)
    assert confirmed.contract.status is ContractStatus.ACTIVE
    url, _ = await h.service.file_url(created.contract.id)
    assert "download=계약서.pdf" in url
    assert h.actions() == [
        "educator.contract.create",
        "educator.contract_file.upload",
        "educator.contract.update",
        "educator.contract.confirm",
    ]


async def test_create_validates_employee_and_file(h: Harness) -> None:
    with pytest.raises(NotFoundError) as employee:
        await h.service.create(h.values(manager_employee_id=new_id()), actor_id=h.actor_id)
    assert employee.value.code == "employee_not_found"
    with pytest.raises(NotFoundError) as missing:
        await h.service.create(h.values(contract_file_id=new_id()), actor_id=h.actor_id)
    assert missing.value.code == "contract_file_not_found"

    file = await h.uploaded_file()
    await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    with pytest.raises(ConflictError) as in_use:
        await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    assert in_use.value.code == "contract_file_in_use"


async def test_replacing_file_keeps_old_record(h: Harness) -> None:
    old = await h.uploaded_file()
    new = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=old.id), actor_id=h.actor_id)

    await h.service.update(created.contract.id, {"contract_file_id": new.id}, actor_id=h.actor_id)

    assert h.files.items[old.id].deleted_at == NOW
    assert old.storage_key not in h.storage.deleted  # S3 객체는 남긴다
    with pytest.raises(NotFoundError):  # 버린 파일은 다시 붙일 수 없다
        await h.service.create(h.values(contract_file_id=old.id), actor_id=h.actor_id)


async def test_confirmed_contract_rules(h: Harness) -> None:
    file = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    contract_id = created.contract.id
    await h.service.confirm(contract_id, actor_id=h.actor_id)

    with pytest.raises(BusinessRuleViolation) as edit:
        await h.service.update(contract_id, {"title": "변경"}, actor_id=h.actor_id)
    assert edit.value.code == "contract_not_editable"
    with pytest.raises(BusinessRuleViolation) as delete:
        await h.service.delete(contract_id, actor_id=h.actor_id)
    assert delete.value.code == "contract_not_deletable"

    other_manager = new_id()
    h.employees.ids.add(other_manager)
    changed = await h.service.update(
        contract_id, {"manager_employee_id": other_manager}, actor_id=h.actor_id
    )
    assert changed.contract.manager_employee_id == other_manager

    terminated = await h.service.terminate(contract_id, actor_id=h.actor_id)
    assert terminated.contract.status is ContractStatus.TERMINATED


async def test_delete_draft_discards_file(h: Harness) -> None:
    file = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)

    await h.service.delete(created.contract.id, actor_id=h.actor_id)

    assert h.contracts.items == {}
    assert h.files.items[file.id].deleted_at == NOW
    assert h.actions()[-1] == "educator.contract.delete"


async def test_expire_ended_contracts(h: Harness) -> None:
    async def active(end_date: date) -> uuid.UUID:
        file = await h.uploaded_file()
        view = await h.service.create(
            h.values(contract_file_id=file.id, end_date=end_date), actor_id=h.actor_id
        )
        await h.service.confirm(view.contract.id, actor_id=h.actor_id)
        return view.contract.id

    yesterday = await active(date(2026, 11, 8))
    today = await active(date(2026, 11, 9))
    # 확정 시점에 이미 끝난 계약은 ENDED로 확정된다
    assert h.contracts.items[yesterday].status is ContractStatus.ENDED

    h.clock.set(NOW + timedelta(days=1))

    assert await h.service.expire_ended() == 1
    assert h.contracts.items[today].status is ContractStatus.ENDED
    assert h.actions()[-1] == "educator.contract.expire"
    assert h.audit_logs.logs[-1].actor_user_id is None
    assert await h.service.expire_ended() == 0  # 멱등


async def test_list_returns_files(h: Harness) -> None:
    file = await h.uploaded_file()
    await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    await h.service.create(h.values(), actor_id=h.actor_id)

    views, total = await h.service.list_contracts(ContractFilter(), limit=20, offset=0)

    assert total == 2
    assert {v.file.id if v.file else None for v in views} == {file.id, None}

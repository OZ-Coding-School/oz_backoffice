import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.access.application.permissions import PermissionScope
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.contract_files import (
    CONTRACT_MAX_BYTES,
    ContractFileUploadService,
)
from app.contexts.educator.application.contracts import ContractService
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.enums import (
    ContractStatus,
    ContractType,
    MentoringTimeBasis,
    PriceUnit,
    SettlementType,
    TerminationReason,
)
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.pending_uploads import RedisPendingUploadStore
from app.core.clock import FixedClock
from app.shared.errors import (
    BusinessRuleViolation,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import (
    FakeAcademyDirectory,
    FakeContractPermissions,
    FakeEmployeeDirectory,
    FakeFileStorage,
    InMemoryAmendmentRepository,
    InMemoryContractFileRepository,
    InMemoryContractRepository,
    InMemoryInstructorRepository,
    InMemoryMentorRepository,
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
        self.mentors = InMemoryMentorRepository()
        self.instructors = InMemoryInstructorRepository()
        self.bootcamp_id = new_id()
        self.cohort_id = new_id()
        self.other_bootcamp_id = new_id()
        self.academy = FakeAcademyDirectory(
            {self.bootcamp_id: [self.cohort_id], self.other_bootcamp_id: []}
        )
        self.permissions = FakeContractPermissions(self.academy)
        self.amendments = InMemoryAmendmentRepository()
        self.service = ContractService(
            contracts=self.contracts,
            amendments=self.amendments,
            academy=self.academy,
            permissions=self.permissions,
            files=self.files,
            mentors=self.mentors,
            instructors=self.instructors,
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
            "contract_type": ContractType.MENTOR,
            "bootcamp_id": self.bootcamp_id,
            "cohort_id": self.cohort_id,
            "contractor_name": "김멘토",
            "contractor_phone": "01012345678",
            "title": "2026 멘토 계약",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "settlement_type": SettlementType.UNIT_PRICE,
            "unit_price": 50000,
            "price_unit": PriceUnit.HOURLY,
            "no_show_pay_amount": 0,
            "mentoring_time_basis": MentoringTimeBasis.ACTUAL_DURATION,
        }
        values.update(overrides)
        return values

    def vendor(self, **overrides: Any) -> dict[str, Any]:
        return self.values(
            contract_type=ContractType.SW,
            contractor_name="(주)오즈",
            contractor_phone=None,
            settlement_type=SettlementType.FIXED,
            total_amount=1_000_000,
            unit_price=None,
            price_unit=None,
            no_show_pay_amount=None,
            mentoring_time_basis=None,
            cohort_id=None,
            **overrides,
        )

    async def signed(self, **overrides: Any) -> uuid.UUID:
        file = await self.uploaded_file()
        view = await self.service.create(
            self.values(contract_file_id=file.id, **overrides), actor_id=self.actor_id
        )
        await self.service.start_progress(view.contract.id, actor_id=self.actor_id)
        await self.service.sign(view.contract.id, actor_id=self.actor_id)
        return view.contract.id

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
async def test_create_draft_then_progress_and_sign(h: Harness) -> None:
    created = await h.service.create(h.values(), actor_id=h.actor_id)
    contract_id = created.contract.id
    assert (created.contract.status, created.file) == (ContractStatus.DRAFT, None)

    file = await h.uploaded_file()
    updated = await h.service.update(
        contract_id, {"contract_file_id": file.id}, actor_id=h.actor_id
    )
    assert updated.file is not None
    assert updated.file.id == file.id

    progressing = await h.service.start_progress(contract_id, actor_id=h.actor_id)
    assert progressing.contract.status is ContractStatus.IN_PROGRESS
    changed = await h.service.update(contract_id, {"unit_price": 60000}, actor_id=h.actor_id)
    assert changed.contract.unit_price == 60000  # 진행 중에도 고칠 수 있다
    signed = await h.service.sign(contract_id, actor_id=h.actor_id)
    assert signed.contract.status is ContractStatus.ACTIVE
    url, _ = await h.service.file_url(contract_id, actor_id=h.actor_id)
    assert "download=계약서.pdf" in url
    assert h.actions() == [
        "educator.mentor.create_pending",
        "educator.contract.create",
        "educator.contract_file.upload",
        "educator.contract.update",
        "educator.contract.start",
        "educator.contract.update",
        "educator.contract.sign",
    ]


async def test_create_validates_employee_file_and_academy(h: Harness) -> None:
    with pytest.raises(NotFoundError) as employee:
        await h.service.create(h.values(manager_employee_id=new_id()), actor_id=h.actor_id)
    assert employee.value.code == "employee_not_found"
    with pytest.raises(NotFoundError) as missing:
        await h.service.create(h.values(contract_file_id=new_id()), actor_id=h.actor_id)
    assert missing.value.code == "contract_file_not_found"
    with pytest.raises(NotFoundError) as bootcamp:
        await h.service.create(h.values(bootcamp_id=new_id()), actor_id=h.actor_id)
    assert bootcamp.value.code == "bootcamp_not_found"
    with pytest.raises(NotFoundError) as cohort:
        await h.service.create(h.values(cohort_id=new_id()), actor_id=h.actor_id)
    assert cohort.value.code == "cohort_not_found"
    with pytest.raises(BusinessRuleViolation) as other:
        await h.service.create(h.values(bootcamp_id=h.other_bootcamp_id), actor_id=h.actor_id)
    assert other.value.code == "cohort_not_in_bootcamp"

    file = await h.uploaded_file()
    await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    with pytest.raises(ConflictError) as in_use:
        await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    assert in_use.value.code == "contract_file_in_use"


async def test_vendor_contract_has_no_mentor(h: Harness) -> None:
    created = await h.service.create(h.vendor(), actor_id=h.actor_id)
    assert (created.contract.contract_type, created.contract.mentor_id) == (ContractType.SW, None)
    assert h.mentors.items == {}
    with pytest.raises(BusinessRuleViolation) as kind:
        await h.service.create(h.vendor(), actor_id=h.actor_id, mentor_id=new_id())
    assert kind.value.code == "contract_type_mismatch"


async def test_replacing_file_keeps_old_record(h: Harness) -> None:
    old = await h.uploaded_file()
    new = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=old.id), actor_id=h.actor_id)

    await h.service.update(created.contract.id, {"contract_file_id": new.id}, actor_id=h.actor_id)

    assert h.files.items[old.id].deleted_at == NOW
    assert old.storage_key not in h.storage.deleted  # S3 객체는 남긴다
    with pytest.raises(NotFoundError):  # 버린 파일은 다시 붙일 수 없다
        await h.service.create(h.values(contract_file_id=old.id), actor_id=h.actor_id)


async def test_signed_contract_rules(h: Harness) -> None:
    contract_id = await h.signed()

    with pytest.raises(BusinessRuleViolation) as edit:
        await h.service.update(contract_id, {"title": "변경"}, actor_id=h.actor_id)
    assert edit.value.code == "contract_not_editable"
    with pytest.raises(BusinessRuleViolation) as delete:
        await h.service.delete(contract_id, actor_id=h.actor_id)
    assert delete.value.code == "contract_not_deletable"
    with pytest.raises(BusinessRuleViolation) as cancel:
        await h.service.cancel(contract_id, reason="취소", on=None, actor_id=h.actor_id)
    assert cancel.value.code == "invalid_contract_transition"

    other_manager = new_id()
    h.employees.ids.add(other_manager)
    changed = await h.service.update(
        contract_id, {"manager_employee_id": other_manager}, actor_id=h.actor_id
    )
    assert changed.contract.manager_employee_id == other_manager

    terminated = await h.service.terminate(
        contract_id,
        reason=TerminationReason.TERMINATED_BY_FAULT,
        detail="연락 두절",
        on=None,
        actor_id=h.actor_id,
    )
    assert (terminated.contract.status, terminated.contract.terminated_on) == (
        ContractStatus.TERMINATED,
        date(2026, 11, 9),
    )


async def test_cancel_in_progress(h: Harness) -> None:
    file = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    await h.service.start_progress(created.contract.id, actor_id=h.actor_id)
    canceled = await h.service.cancel(
        created.contract.id, reason="조건 불일치", on=date(2026, 11, 8), actor_id=h.actor_id
    )
    assert (canceled.contract.status, canceled.contract.canceled_on) == (
        ContractStatus.CANCELED,
        date(2026, 11, 8),
    )


async def test_amend_signed_contract(h: Harness) -> None:
    contract_id = await h.signed(start_date=date(2026, 12, 1))
    assert h.contracts.items[contract_id].status is ContractStatus.SIGNED
    file = await h.uploaded_file()

    view = await h.service.amend(
        contract_id,
        {"unit_price": 70000, "start_date": date(2026, 11, 1), "title": "2026 멘토 계약"},
        amended_on=date(2026, 11, 9),
        reason="단가 인상",
        contract_file_id=file.id,
        actor_id=h.actor_id,
    )

    # 바뀐 항목만 남는다 (같은 값인 제목은 빠진다)
    assert view.amendment.before == {"unit_price": 50000, "start_date": "2026-12-01"}
    assert view.amendment.after == {"unit_price": 70000, "start_date": "2026-11-01"}
    assert view.file is not None
    contract = h.contracts.items[contract_id]
    # 시작일이 지나 바로 이행 중으로
    assert (contract.unit_price, contract.status) == (70000, ContractStatus.ACTIVE)
    assert [
        v.amendment.id for v in await h.service.amendments(contract_id, actor_id=h.actor_id)
    ] == [view.amendment.id]
    url, _ = await h.service.amendment_file_url(contract_id, view.amendment.id, actor_id=h.actor_id)
    assert "download=계약서.pdf" in url
    assert h.actions()[-1] == "educator.contract.amend"

    with pytest.raises(BusinessRuleViolation) as same:
        await h.service.amend(
            contract_id,
            {"unit_price": 70000},
            amended_on=date(2026, 11, 9),
            reason="같은 값",
            contract_file_id=None,
            actor_id=h.actor_id,
        )
    assert same.value.code == "amendment_no_changes"
    with pytest.raises(ConflictError) as reused:  # 변경 계약서는 다시 쓸 수 없다
        await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    assert reused.value.code == "contract_file_in_use"


async def test_amend_phone_updates_pending_mentor(h: Harness) -> None:
    contract_id = await h.signed()
    await h.service.amend(
        contract_id,
        {"contractor_phone": "010-2222-3333"},
        amended_on=date(2026, 11, 9),
        reason="번호 변경",
        contract_file_id=None,
        actor_id=h.actor_id,
    )
    mentor_id = h.contracts.items[contract_id].mentor_id or new_id()
    assert h.mentors.items[mentor_id].contact_phone == "01022223333"


async def test_delete_draft_discards_file(h: Harness) -> None:
    file = await h.uploaded_file()
    created = await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)

    await h.service.delete(created.contract.id, actor_id=h.actor_id)

    assert h.contracts.items == {}
    assert h.files.items[file.id].deleted_at == NOW
    # 계약이 하나도 남지 않은 가입 전 멘토는 함께 지운다 (A104)
    assert h.actions()[-2:] == ["educator.contract.delete", "educator.mentor.delete_pending"]
    assert h.mentors.items == {}


async def test_advance_due_contracts(h: Harness) -> None:
    ending = await h.signed(end_date=date(2026, 11, 9))
    starting = await h.signed(start_date=date(2026, 11, 10))
    finished = await h.signed(end_date=date(2026, 11, 8))
    # 완료 시점에 이미 끝난 계약은 바로 ENDED
    assert h.contracts.items[finished].status is ContractStatus.ENDED
    assert h.contracts.items[starting].status is ContractStatus.SIGNED

    h.clock.set(NOW + timedelta(days=1))

    assert await h.service.advance_due() == 2
    assert h.contracts.items[ending].status is ContractStatus.ENDED
    assert h.contracts.items[starting].status is ContractStatus.ACTIVE
    assert h.actions()[-1] == "educator.contract.advance"
    assert h.audit_logs.logs[-1].actor_user_id is None
    assert await h.service.advance_due() == 0  # 멱등


async def test_end_contract_without_end_date(h: Harness) -> None:
    contract_id = await h.signed(start_date=None, end_date=None)
    ended = await h.service.end(contract_id, actor_id=h.actor_id)
    assert ended.contract.status is ContractStatus.ENDED


async def test_list_returns_files(h: Harness) -> None:
    file = await h.uploaded_file()
    await h.service.create(h.values(contract_file_id=file.id), actor_id=h.actor_id)
    await h.service.create(h.values(), actor_id=h.actor_id)

    listed = await h.service.list_contracts(
        ContractFilter(), actor_id=h.actor_id, limit=20, offset=0
    )

    assert listed.total == 2
    assert {v.file.id if v.file else None for v in listed.views} == {file.id, None}


async def test_scope_limits_contracts(h: Harness) -> None:
    """담당 범위 (A109⑦): 조회 범위 밖은 404, 관리 범위 밖은 403."""
    common = await h.service.create(h.vendor(), actor_id=h.actor_id)  # 과정 공통
    cohort = await h.service.create(h.values(), actor_id=h.actor_id)  # 기수 계약
    other = await h.service.create(h.vendor(bootcamp_id=h.other_bootcamp_id), actor_id=h.actor_id)

    async def visible() -> set[uuid.UUID]:
        listed = await h.service.list_contracts(
            ContractFilter(), actor_id=h.actor_id, limit=20, offset=0
        )
        return {v.contract.id for v in listed.views}

    # 과정 담당: 그 과정의 공통 계약과 기수 계약
    h.permissions.scopes = {
        code: PermissionScope(bootcamp_ids=frozenset({h.bootcamp_id}))
        for code in ("educator.contract.read", "educator.contract.manage")
    }
    assert await visible() == {common.contract.id, cohort.contract.id}
    # 기수 담당: 그 기수 계약만
    h.permissions.scopes = {
        code: PermissionScope(cohort_ids=frozenset({h.cohort_id}))
        for code in ("educator.contract.read", "educator.contract.manage")
    }
    assert await visible() == {cohort.contract.id}
    with pytest.raises(NotFoundError):
        await h.service.get(common.contract.id, actor_id=h.actor_id)
    with pytest.raises(PermissionDeniedError):  # 범위 밖 과정에는 만들 수 없다
        await h.service.create(h.vendor(), actor_id=h.actor_id)
    # 조회만 넓으면 볼 수는 있지만 바꿀 수 없다
    h.permissions.scopes["educator.contract.read"] = PermissionScope(is_global=True)
    assert (await h.service.get(other.contract.id, actor_id=h.actor_id)).contract.id
    with pytest.raises(PermissionDeniedError):
        await h.service.update(other.contract.id, {"title": "변경"}, actor_id=h.actor_id)


async def test_move_between_mentors_regardless_of_status(h: Harness) -> None:
    mentor = Mentor(user_id=new_id())
    other = Mentor(user_id=new_id())
    await h.mentors.save(mentor)
    await h.mentors.save(other)
    contract_id = await h.signed()
    pending_id = h.contracts.items[contract_id].mentor_id
    await h.service.terminate(  # 끝난 계약도 옮길 수 있다
        contract_id,
        reason=TerminationReason.TERMINATED_BY_UNILATERAL,
        detail=None,
        on=None,
        actor_id=h.actor_id,
    )

    linked = await h.service.link(contract_id, mentor_id=mentor.id, actor_id=h.actor_id)
    assert linked.contract.mentor_id == mentor.id
    # 마지막 계약이 옮겨 간 가입 전 멘토는 지운다 (A104)
    assert pending_id not in h.mentors.items
    changed = await h.service.link(contract_id, mentor_id=other.id, actor_id=h.actor_id)
    assert changed.contract.mentor_id == other.id
    assert mentor.id in h.mentors.items  # 가입한 멘토는 남는다
    with pytest.raises(BusinessRuleViolation) as unlink:
        await h.service.link(contract_id, actor_id=h.actor_id)
    assert unlink.value.code == "mentor_contract_unlink_forbidden"


async def test_mentor_contract_belongs_to_a_mentor(h: Harness) -> None:
    """만들 때 지정한 멘토 → 이름·휴대폰이 같은 멘토 하나 → 새 가입 전 멘토 (A104)."""
    first = await h.service.create(h.values(), actor_id=h.actor_id)
    pending = h.mentors.items[first.contract.mentor_id or new_id()]
    assert (pending.user_id, pending.contact_name, pending.contact_phone, pending.is_active) == (
        None,
        "김멘토",
        "01012345678",
        False,
    )
    # 같은 사람이면 같은 가입 전 멘토에 붙는다
    second = await h.service.create(h.values(title="재계약"), actor_id=h.actor_id)
    assert second.contract.mentor_id == pending.id
    # 지정하면 그 멘토
    registered = Mentor(user_id=new_id())
    await h.mentors.save(registered)
    chosen = await h.service.create(h.values(), actor_id=h.actor_id, mentor_id=registered.id)
    assert chosen.contract.mentor_id == registered.id
    with pytest.raises(NotFoundError):
        await h.service.create(h.values(), actor_id=h.actor_id, mentor_id=new_id())
    # 같은 사람이 둘이면 고를 수 없다
    await h.mentors.add(Mentor.pending(name="이멘토", phone="01099998888"))
    await h.mentors.add(Mentor.pending(name="이멘토", phone="01099998888"))
    with pytest.raises(ConflictError) as ambiguous:
        await h.service.create(
            h.values(contractor_name="이멘토", contractor_phone="01099998888"),
            actor_id=h.actor_id,
        )
    assert ambiguous.value.code == "ambiguous_mentor"


async def test_editing_contractor_updates_pending_mentor(h: Harness) -> None:
    created = await h.service.create(h.values(), actor_id=h.actor_id)
    await h.service.update(
        created.contract.id,
        {"contractor_name": "김멘토2", "contractor_phone": "010-1111-2222"},
        actor_id=h.actor_id,
    )
    pending = h.mentors.items[created.contract.mentor_id or new_id()]
    assert (pending.contact_name, pending.contact_phone) == ("김멘토2", "01011112222")
    with pytest.raises(BusinessRuleViolation) as kind:
        await h.service.update(
            created.contract.id,
            {
                "contract_type": ContractType.INSTRUCTOR,
                "no_show_pay_amount": None,
                "mentoring_time_basis": None,
            },
            actor_id=h.actor_id,
        )
    assert kind.value.code == "contract_type_mismatch"


async def test_link_requires_matching_existing_profile(h: Harness) -> None:
    created = await h.service.create(h.values(), actor_id=h.actor_id)
    contract_id = created.contract.id
    instructor_id = new_id()
    h.instructors.ids.add(instructor_id)

    with pytest.raises(BusinessRuleViolation) as kind:
        await h.service.link(contract_id, instructor_id=instructor_id, actor_id=h.actor_id)
    assert kind.value.code == "contract_type_mismatch"
    with pytest.raises(NotFoundError) as missing:
        await h.service.link(contract_id, mentor_id=new_id(), actor_id=h.actor_id)
    assert missing.value.code == "mentor_not_found"

    instructor_contract = await h.service.create(
        h.values(
            contract_type=ContractType.INSTRUCTOR,
            no_show_pay_amount=None,
            mentoring_time_basis=None,
        ),
        actor_id=h.actor_id,
    )
    linked = await h.service.link(
        instructor_contract.contract.id, instructor_id=instructor_id, actor_id=h.actor_id
    )
    assert linked.contract.instructor_id == instructor_id
    with pytest.raises(NotFoundError) as no_instructor:
        await h.service.link(
            instructor_contract.contract.id, instructor_id=new_id(), actor_id=h.actor_id
        )
    assert no_instructor.value.code == "instructor_not_found"


async def test_list_counts_by_type_and_bootcamp_common(h: Harness) -> None:
    """A112: 종류별 건수는 종류 필터를 무시하고, 기수 필터는 과정 공통 계약을 함께 볼 수 있다."""
    common = await h.service.create(h.vendor(), actor_id=h.actor_id)  # 과정 공통 SW
    cohort = await h.service.create(h.values(), actor_id=h.actor_id)  # 기수 멘토 계약
    await h.service.create(h.vendor(bootcamp_id=h.other_bootcamp_id), actor_id=h.actor_id)

    only_cohort = await h.service.list_contracts(
        ContractFilter(cohort_id=h.cohort_id), actor_id=h.actor_id, limit=20, offset=0
    )
    assert {v.contract.id for v in only_cohort.views} == {cohort.contract.id}

    with_common = await h.service.list_contracts(
        ContractFilter(cohort_id=h.cohort_id, contract_types=frozenset({ContractType.MENTOR})),
        actor_id=h.actor_id,
        limit=20,
        offset=0,
        include_bootcamp_common=True,
    )
    assert {v.contract.id for v in with_common.views} == {cohort.contract.id}
    assert with_common.counts[ContractType.MENTOR] == 1
    assert with_common.counts[common.contract.contract_type] == 1
    assert sum(with_common.counts.values()) == 2

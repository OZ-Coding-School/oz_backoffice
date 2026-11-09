"""계약서 업로드 (decisions A26).

① 업로드 요청: 파일 이름을 검사하고 객체 키 `contracts/<uuid7>.pdf`와 presigned POST
   (application/pdf, 10MB 이하)를 발급한다. 요청 정보는 대기 저장소(Redis)에 TTL로 둔다.
② 브라우저가 S3로 직접 올린다.
③ 확정: 요청한 사람만, 한 번만 확정한다. `head`로 크기·타입을 확인하고 앞 5바이트가 `%PDF-`인지
   본다. 맞지 않으면 객체를 지우고 거부한다. 통과하면 `contract_files`를 만든다.
   아직 올리지 않았으면(객체 없음) 대기 정보를 되돌려 다시 확정할 수 있게 한다.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.ports import FileStorage
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.repositories import ContractFileRepository
from app.contexts.educator.domain.uploads import PendingUpload, PendingUploadStore
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id

PDF_CONTENT_TYPE = "application/pdf"
PDF_EXTENSION = "pdf"
PDF_MAGIC = b"%PDF-"
CONTRACT_MAX_BYTES = 10 * 1024 * 1024
FILE_NAME_MAX_LENGTH = 100
# presigned POST가 만료된 뒤에도 업로드 마무리·확정 요청이 도착할 여유
CONFIRM_GRACE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class UploadTicket:
    upload_id: uuid.UUID
    url: str
    fields: dict[str, str]
    expires_at: datetime
    max_bytes: int


def parse_pdf_file_name(raw: str) -> tuple[str, str]:
    """원본 파일 이름을 검사하고 (이름, 확장자)를 돌려준다. 100자를 넘으면 거부한다."""
    name = raw.strip()
    if not name:
        raise BusinessRuleViolation("파일 이름이 비어 있습니다.", code="invalid_file_name")
    if len(name) > FILE_NAME_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"파일 이름은 {FILE_NAME_MAX_LENGTH}자 이하여야 합니다.", code="file_name_too_long"
        )
    if any(ch in "/\\" or ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise BusinessRuleViolation(
            "파일 이름에 쓸 수 없는 문자가 있습니다.", code="invalid_file_name"
        )
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or ext.lower() != PDF_EXTENSION:
        raise BusinessRuleViolation(
            "계약서는 PDF 파일만 올릴 수 있습니다.", code="unsupported_file_type"
        )
    return name, PDF_EXTENSION


class ContractFileUploadService:
    def __init__(
        self,
        *,
        storage: FileStorage,
        pending: PendingUploadStore,
        files: ContractFileRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._storage = storage
        self._pending = pending
        self._files = files
        self._audit = audit
        self._uow = uow
        self._clock = clock

    async def request_upload(self, file_name: str, *, actor_id: uuid.UUID) -> UploadTicket:
        name, ext = parse_pdf_file_name(file_name)
        now = self._clock.now()
        key = f"contracts/{new_id()}.{ext}"
        post = await self._storage.presign_post(
            key, content_type=PDF_CONTENT_TYPE, max_bytes=CONTRACT_MAX_BYTES, now=now
        )
        upload = PendingUpload(
            id=new_id(),
            requested_by=actor_id,
            storage_key=key,
            file_name=name,
            file_ext=ext,
            content_type=PDF_CONTENT_TYPE,
            max_bytes=CONTRACT_MAX_BYTES,
            expires_at=post.expires_at + CONFIRM_GRACE,
        )
        await self._pending.put(upload, ttl_seconds=_seconds_until(upload.expires_at, now))
        return UploadTicket(
            upload_id=upload.id,
            url=post.url,
            fields=post.fields,
            expires_at=post.expires_at,
            max_bytes=CONTRACT_MAX_BYTES,
        )

    async def confirm(self, upload_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractFile:
        upload = await self._pending.take(actor_id, upload_id)
        if upload is None:
            raise NotFoundError(
                "업로드 요청을 찾을 수 없거나 만료되었습니다. 다시 업로드하세요.",
                code="upload_not_found",
            )
        info = await self._storage.head(upload.storage_key)
        if info is None:
            now = self._clock.now()
            if upload.expires_at > now:  # 아직 올리는 중일 수 있으니 다시 확정할 수 있게 둔다
                await self._pending.put(upload, ttl_seconds=_seconds_until(upload.expires_at, now))
            raise BusinessRuleViolation(
                "업로드된 파일이 없습니다. 업로드를 마친 뒤 확정하세요.",
                code="upload_not_completed",
            )
        prefix = await self._storage.read_prefix(upload.storage_key, len(PDF_MAGIC))
        valid = (
            0 < info.size <= upload.max_bytes
            and info.content_type == upload.content_type
            and prefix == PDF_MAGIC
        )
        if not valid:
            await self._storage.delete(upload.storage_key)
            raise BusinessRuleViolation(
                "PDF 파일이 아니거나 허용 크기를 넘었습니다.", code="invalid_contract_file"
            )
        file = ContractFile(
            file_name=upload.file_name,
            file_ext=upload.file_ext,
            file_size=info.size,
            storage_key=upload.storage_key,
        )
        async with self._uow:
            await self._files.add(file)
            await self._audit.record(
                actor_user_id=actor_id,
                action="educator.contract_file.upload",
                target_type="contract_file",
                target_id=file.id,
                after={"file_name": file.file_name, "file_size": file.file_size},
            )
        saved = await self._files.get(file.id)  # DB가 정한 created_at까지 담아 돌려준다
        return saved or file


def _seconds_until(at: datetime, now: datetime) -> int:
    return max(1, int((at - now).total_seconds()))

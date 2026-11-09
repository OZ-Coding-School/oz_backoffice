"""계약서 업로드 (decisions A26). 공통 흐름은 `uploads.DirectUploads`.

- 요청: 원본 파일 이름(PDF, 100자 이하)을 검사하고 `contracts/<uuid7>.pdf` 업로드를 발급한다
  (application/pdf, 10MB 이하).
- 확정: 크기·타입과 앞 5바이트(`%PDF-`)를 확인한 뒤 `contract_files`를 만든다.
"""

import uuid

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.uploads import DirectUploads, UploadSpec, UploadTicket
from app.contexts.educator.domain.entities import ContractFile
from app.contexts.educator.domain.repositories import ContractFileRepository
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation

PDF_EXTENSION = "pdf"
PDF_CONTENT_TYPE = "application/pdf"
PDF_MAGIC = b"%PDF-"
CONTRACT_MAX_BYTES = 10 * 1024 * 1024
FILE_NAME_MAX_LENGTH = 100

CONTRACT_UPLOAD = UploadSpec(
    purpose="contract_file",
    key_prefix="contracts/",
    extensions={PDF_CONTENT_TYPE: PDF_EXTENSION},
    max_bytes=CONTRACT_MAX_BYTES,
    magic_length=len(PDF_MAGIC),
    is_valid_format=lambda head, _content_type: head == PDF_MAGIC,
    invalid_code="invalid_contract_file",
    invalid_message="PDF 파일이 아니거나 허용 크기를 넘었습니다.",
)


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
        uploads: DirectUploads,
        files: ContractFileRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._uploads = uploads
        self._files = files
        self._audit = audit
        self._uow = uow

    async def request_upload(self, file_name: str, *, actor_id: uuid.UUID) -> UploadTicket:
        name, _ = parse_pdf_file_name(file_name)
        return await self._uploads.issue(
            CONTRACT_UPLOAD, actor_id=actor_id, content_type=PDF_CONTENT_TYPE, file_name=name
        )

    async def confirm(self, upload_id: uuid.UUID, *, actor_id: uuid.UUID) -> ContractFile:
        received = await self._uploads.receive(CONTRACT_UPLOAD, upload_id, actor_id=actor_id)
        file = ContractFile(
            file_name=received.upload.file_name,
            file_ext=received.upload.file_ext,
            file_size=received.info.size,
            storage_key=received.upload.storage_key,
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

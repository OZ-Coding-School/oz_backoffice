"""업로드 요청 ~ 확정 사이에 보관하는 정보와 저장소 Protocol (decisions A26)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class PendingUpload:
    """업로드 요청 ~ 확정 사이에 보관하는 정보 (A26)."""

    id: uuid.UUID
    # 업로드 용도 (예: `contract_file`, `mentor_image:<멘토 ID>`). 다른 용도로 확정할 수 없다
    purpose: str
    requested_by: uuid.UUID
    storage_key: str
    file_name: str
    file_ext: str
    content_type: str
    max_bytes: int
    expires_at: datetime


class PendingUploadStore(Protocol):
    async def put(self, upload: PendingUpload, *, ttl_seconds: int) -> None: ...
    async def take(
        self, requested_by: uuid.UUID, purpose: str, upload_id: uuid.UUID
    ) -> PendingUpload | None:
        """요청자의 대기 업로드를 꺼내며 지운다(한 번만 확정). 다른 사람·다른 용도면 None."""
        ...

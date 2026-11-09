"""브라우저 → S3 직접 업로드 공통 흐름 (decisions A26, A28).

① 발급: presigned POST(Content-Type 고정, 크기 상한)를 만들고 요청 정보를 대기 저장소에 TTL로 둔다.
② 브라우저가 S3로 직접 올린다.
③ 수령: 요청자·용도가 같은 대기 정보를 한 번만 꺼낸다. `head`로 크기·타입을, 앞부분으로 파일 형식
   (매직 바이트)을 확인한다. 맞지 않으면 객체를 지우고 거부한다. 아직 올리지 않았으면 대기 정보를
   되돌려 다시 확정할 수 있게 한다.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.contexts.educator.application.ports import FileStorage
from app.contexts.educator.domain.uploads import PendingUpload, PendingUploadStore
from app.core.clock import Clock
from app.integrations.s3 import ObjectInfo
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id

# presigned POST가 만료된 뒤에도 업로드 마무리·확정 요청이 도착할 여유
CONFIRM_GRACE = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class UploadTicket:
    upload_id: uuid.UUID
    url: str
    fields: dict[str, str]
    expires_at: datetime
    max_bytes: int


@dataclass(frozen=True, slots=True)
class UploadSpec:
    """업로드 용도별 허용 조건."""

    purpose: str
    key_prefix: str  # 예: "contracts/"
    file_ext: str
    content_type: str
    max_bytes: int
    magic_length: int
    is_valid_format: Callable[[bytes], bool]
    invalid_code: str
    invalid_message: str


@dataclass(frozen=True, slots=True)
class ReceivedUpload:
    upload: PendingUpload
    info: ObjectInfo


class DirectUploads:
    def __init__(self, *, storage: FileStorage, pending: PendingUploadStore, clock: Clock) -> None:
        self._storage = storage
        self._pending = pending
        self._clock = clock

    async def issue(
        self, spec: UploadSpec, *, actor_id: uuid.UUID, file_name: str = ""
    ) -> UploadTicket:
        now = self._clock.now()
        key = f"{spec.key_prefix}{new_id()}.{spec.file_ext}"
        post = await self._storage.presign_post(
            key, content_type=spec.content_type, max_bytes=spec.max_bytes, now=now
        )
        upload = PendingUpload(
            id=new_id(),
            purpose=spec.purpose,
            requested_by=actor_id,
            storage_key=key,
            file_name=file_name,
            file_ext=spec.file_ext,
            content_type=spec.content_type,
            max_bytes=spec.max_bytes,
            expires_at=post.expires_at + CONFIRM_GRACE,
        )
        await self._pending.put(upload, ttl_seconds=_seconds_until(upload.expires_at, now))
        return UploadTicket(
            upload_id=upload.id,
            url=post.url,
            fields=post.fields,
            expires_at=post.expires_at,
            max_bytes=spec.max_bytes,
        )

    async def receive(
        self, spec: UploadSpec, upload_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> ReceivedUpload:
        upload = await self._pending.take(actor_id, spec.purpose, upload_id)
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
        prefix = await self._storage.read_prefix(upload.storage_key, spec.magic_length)
        valid = (
            0 < info.size <= upload.max_bytes
            and info.content_type == upload.content_type
            and prefix is not None
            and spec.is_valid_format(prefix)
        )
        if not valid:
            await self._storage.delete(upload.storage_key)
            raise BusinessRuleViolation(spec.invalid_message, code=spec.invalid_code)
        return ReceivedUpload(upload, info)


def _seconds_until(at: datetime, now: datetime) -> int:
    return max(1, int((at - now).total_seconds()))

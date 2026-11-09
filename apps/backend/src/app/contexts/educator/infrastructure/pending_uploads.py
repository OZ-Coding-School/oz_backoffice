"""업로드 요청 ~ 확정 사이의 대기 정보 (Redis, decisions A26).

키 `oz:educator:upload:<요청자 ID>:<업로드 ID>`. 요청자 ID를 키에 넣어 다른 사람은 꺼낼 수 없고,
GETDEL로 꺼내 한 번만 확정되게 한다.
"""

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from app.contexts.educator.domain.uploads import PendingUpload

if TYPE_CHECKING:
    from redis.asyncio import Redis

_PREFIX = "oz:educator:upload:"


def _key(requested_by: uuid.UUID, upload_id: uuid.UUID) -> str:
    return f"{_PREFIX}{requested_by}:{upload_id}"


class RedisPendingUploadStore:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis

    async def put(self, upload: PendingUpload, *, ttl_seconds: int) -> None:
        data = asdict(upload)
        data.update(
            id=str(upload.id),
            requested_by=str(upload.requested_by),
            expires_at=upload.expires_at.isoformat(),
        )
        await self._redis.set(
            _key(upload.requested_by, upload.id), json.dumps(data), ex=ttl_seconds
        )

    async def take(self, requested_by: uuid.UUID, upload_id: uuid.UUID) -> PendingUpload | None:
        raw = await self._redis.getdel(_key(requested_by, upload_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return PendingUpload(
            id=uuid.UUID(data["id"]),
            requested_by=uuid.UUID(data["requested_by"]),
            storage_key=data["storage_key"],
            file_name=data["file_name"],
            file_ext=data["file_ext"],
            content_type=data["content_type"],
            max_bytes=int(data["max_bytes"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )

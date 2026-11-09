"""educator 응용 서비스가 쓰는 외부 의존 (파일 저장소, 직원 조회).

업로드 대기 저장소 Protocol은 인프라가 구현하므로 `domain.uploads`에 둔다.
"""

import uuid
from datetime import datetime
from typing import Protocol

from app.integrations.s3 import ObjectInfo, PresignedPost


class FileStorage(Protocol):
    """S3 어댑터(`app.integrations.s3.S3Storage`)가 만족한다."""

    async def presign_post(
        self, key: str, *, content_type: str, max_bytes: int, now: datetime
    ) -> PresignedPost: ...
    async def presign_get(self, key: str, *, download_name: str | None = None) -> str: ...
    async def head(self, key: str) -> ObjectInfo | None: ...
    async def read_prefix(self, key: str, length: int) -> bytes | None: ...
    async def delete(self, key: str) -> None: ...


class EmployeeDirectory(Protocol):
    """organization 공개 조회 (`EmployeeQueries`, app.state.employee_queries)."""

    async def exists(self, employee_id: uuid.UUID) -> bool: ...

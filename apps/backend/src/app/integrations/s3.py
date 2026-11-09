"""S3 객체 저장소 어댑터 (aioboto3, decisions B8·C5·C7).

- 비공개 버킷 1개를 prefix(`contracts/`, `profiles/` …)로 나눠 쓴다. DB에는 객체 키만 저장한다.
- 업로드: 서버가 presigned POST(크기 상한·Content-Type 조건)를 발급 → 브라우저가 S3로 직접 올림
  → 서버가 `head`로 크기·타입을 확인하고 확정한다.
- 다운로드: presigned GET URL만 제공한다.
- 서버가 S3를 호출할 때는 `endpoint_url`, 브라우저에 줄 URL은 `public_endpoint_url`로 서명한다.
  서명에 Host가 들어가므로 두 주소가 다르면(로컬 compose: `s3:4566` / `localhost:4566`)
  공개 주소로 서명해야 브라우저에서 검증된다. 운영은 둘 다 비우고 AWS 기본 엔드포인트를 쓴다.
- 연결·서비스 오류는 `StorageError`(503)로 바꿔 올린다. 없는 객체는 `head`가 None을 돌려준다.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import aioboto3
from aiobotocore.config import AioConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.shared.errors import ServiceUnavailableError

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

# path-style: 에뮬레이터(floci)와 운영 S3에서 같은 URL 형태를 쓴다
_CONFIG = AioConfig(signature_version="s3v4", s3={"addressing_style": "path"})
_NOT_FOUND = {"404", "NoSuchKey", "NotFound"}


class StorageError(ServiceUnavailableError):
    default_code = "storage_unavailable"


@dataclass(frozen=True, slots=True)
class PresignedPost:
    """브라우저가 `url`로 multipart/form-data POST를 보낸다.

    `fields`를 모두 넣고 파일은 맨 끝 `file` 필드로 보낸다.
    """

    url: str
    fields: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    size: int
    content_type: str | None


@dataclass(frozen=True, slots=True)
class S3Settings:
    bucket: str
    region: str
    endpoint_url: str | None = None
    public_endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    presigned_get_ttl_seconds: int = 600
    presigned_post_ttl_seconds: int = 600


def content_disposition(filename: str) -> str:
    """다운로드 파일 이름 헤더 (RFC 6266/5987). 한글 이름은 filename*로 넘긴다."""
    ascii_fallback = filename.encode("ascii", "replace").decode().replace('"', "_")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


class S3Storage:
    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.access_key_id,
            aws_secret_access_key=settings.secret_access_key,
            region_name=settings.region,
        )

    @property
    def bucket(self) -> str:
        return self._settings.bucket

    @asynccontextmanager
    async def _client(self, *, public: bool = False) -> AsyncIterator["S3Client"]:
        endpoint = self._settings.endpoint_url
        if public and self._settings.public_endpoint_url:
            endpoint = self._settings.public_endpoint_url
        async with self._session.client("s3", endpoint_url=endpoint, config=_CONFIG) as client:
            yield client

    async def presign_post(
        self, key: str, *, content_type: str, max_bytes: int, now: datetime
    ) -> PresignedPost:
        """크기(1 ~ max_bytes)와 Content-Type을 고정한 업로드 서명. S3가 조건 위반을 거부한다."""
        ttl = self._settings.presigned_post_ttl_seconds
        async with self._client(public=True) as client:
            post = await client.generate_presigned_post(
                Bucket=self.bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, max_bytes],
                ],
                ExpiresIn=ttl,
            )
        fields: dict[str, Any] = post["fields"]
        return PresignedPost(
            url=post["url"],
            fields={name: str(value) for name, value in fields.items()},
            expires_at=now + timedelta(seconds=ttl),
        )

    async def presign_get(self, key: str, *, download_name: str | None = None) -> str:
        """다운로드 URL. download_name을 주면 그 이름으로 저장되게 Content-Disposition을 붙인다."""
        params: dict[str, str] = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = content_disposition(download_name)
        async with self._client(public=True) as client:
            return await client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=self._settings.presigned_get_ttl_seconds
            )

    async def head(self, key: str) -> ObjectInfo | None:
        try:
            async with self._client() as client:
                head = await client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in _NOT_FOUND:
                return None
            raise StorageError("파일 저장소에 연결할 수 없습니다.") from exc
        except BotoCoreError as exc:
            raise StorageError("파일 저장소에 연결할 수 없습니다.") from exc
        return ObjectInfo(size=head["ContentLength"], content_type=head.get("ContentType"))

    async def delete(self, key: str) -> None:
        """객체를 지운다. 없는 객체를 지워도 오류가 아니다(S3 동작과 같음)."""
        try:
            async with self._client() as client:
                await client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError("파일 저장소에 연결할 수 없습니다.") from exc

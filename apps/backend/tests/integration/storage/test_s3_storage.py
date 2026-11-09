"""S3 어댑터 + 백오피스가 쓰는 S3 시나리오 (decisions R7 실측 항목).

에뮬레이터는 인증을 강제하므로(서명 없는·위조 서명 요청은 403) 운영 S3와 같은 조건으로 검사한다.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aioboto3
import httpx
import pytest
from aiobotocore.config import AioConfig

from app.core.config import Settings
from app.core.storage import s3_settings
from app.integrations.s3 import PresignedPost, S3Storage
from app.shared.ids import new_id
from tests.s3_bucket import CORS_ORIGIN

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 9, tzinfo=UTC)
PDF = b"%PDF-1.7\n" + b"0" * 100


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10) as client:
        yield client


@pytest.fixture
async def raw_s3(settings: Settings, s3_bucket: str) -> AsyncIterator["S3Client"]:
    """어댑터에 없는 S3 기능(멀티파트, Range) 확인용 클라이언트."""
    session = aioboto3.Session(
        aws_access_key_id="test", aws_secret_access_key="test", region_name=settings.aws_region
    )
    config = AioConfig(signature_version="s3v4", s3={"addressing_style": "path"})
    async with session.client("s3", endpoint_url=settings.s3_endpoint_url, config=config) as c:
        yield c


def _key(prefix: str = "contracts", ext: str = "pdf") -> str:
    return f"{prefix}/{new_id()}.{ext}"


async def _upload(
    http: httpx.AsyncClient,
    post: PresignedPost,
    body: bytes,
    *,
    content_type: str = "application/pdf",
    fields: dict[str, str] | None = None,
) -> httpx.Response:
    return await http.post(
        post.url,
        data=fields or post.fields,
        files={"file": ("contract.pdf", body, content_type)},
    )


async def test_presigned_post_upload_then_head(storage: S3Storage, http: httpx.AsyncClient) -> None:
    key = _key()
    post = await storage.presign_post(key, content_type="application/pdf", max_bytes=1024, now=NOW)
    assert post.expires_at == NOW.replace(minute=10)

    response = await _upload(http, post, PDF)

    assert response.status_code in (200, 201, 204), response.text
    info = await storage.head(key)
    assert info is not None
    assert (info.size, info.content_type) == (len(PDF), "application/pdf")


async def test_presigned_post_rejects_oversize_and_wrong_type(
    storage: S3Storage, http: httpx.AsyncClient
) -> None:
    key = _key()
    post = await storage.presign_post(key, content_type="application/pdf", max_bytes=64, now=NOW)

    oversize = await _upload(http, post, PDF)
    wrong_type = await _upload(
        http,
        post,
        b"MZ",
        content_type="application/x-msdownload",
        fields={**post.fields, "Content-Type": "application/x-msdownload"},
    )
    forged = await _upload(
        http,
        post,
        PDF[:32],
        fields={**post.fields, "x-amz-signature": "0" * len(post.fields["x-amz-signature"])},
    )

    assert oversize.status_code >= 400
    assert wrong_type.status_code >= 400
    assert forged.status_code >= 400
    assert await storage.head(key) is None


async def test_presigned_get_and_private_bucket(
    storage: S3Storage, raw_s3: "S3Client", http: httpx.AsyncClient, settings: Settings
) -> None:
    key = _key()
    await raw_s3.put_object(Bucket=storage.bucket, Key=key, Body=PDF, ContentType="application/pdf")

    url = await storage.presign_get(key, download_name="계약서 2026.pdf")
    ok = await http.get(url)
    forged = await http.get(url[:-4] + "0000")
    unsigned = await http.get(f"{settings.s3_endpoint_url}/{storage.bucket}/{key}")

    assert ok.status_code == 200
    assert ok.content == PDF
    assert "filename*=UTF-8''%EA%B3%84%EC%95%BD%EC%84%9C%202026.pdf" in ok.headers.get(
        "content-disposition", ""
    )
    assert forged.status_code in (401, 403)
    assert unsigned.status_code in (401, 403)


async def test_presigned_get_expires(
    settings: Settings, s3_bucket: str, raw_s3: "S3Client", http: httpx.AsyncClient
) -> None:
    from dataclasses import replace

    storage = S3Storage(replace(s3_settings(settings), presigned_get_ttl_seconds=1))
    key = _key()
    await raw_s3.put_object(Bucket=s3_bucket, Key=key, Body=PDF)

    url = await storage.presign_get(key)
    await asyncio.sleep(2.5)

    assert (await http.get(url)).status_code in (400, 401, 403)


async def test_head_missing_and_delete(storage: S3Storage, raw_s3: "S3Client") -> None:
    key = _key()
    assert await storage.head(key) is None
    await storage.delete(key)  # 없는 객체를 지워도 오류가 아니다

    await raw_s3.put_object(Bucket=storage.bucket, Key=key, Body=PDF)
    await storage.delete(key)

    assert await storage.head(key) is None


async def test_cors_preflight(
    storage: S3Storage, http: httpx.AsyncClient, settings: Settings
) -> None:
    url = f"{settings.s3_endpoint_url}/{storage.bucket}"
    allowed = await http.options(
        url, headers={"Origin": CORS_ORIGIN, "Access-Control-Request-Method": "POST"}
    )
    denied = await http.options(
        url, headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"}
    )

    assert allowed.headers.get("access-control-allow-origin") in (CORS_ORIGIN, "*")
    assert denied.headers.get("access-control-allow-origin") not in ("http://evil.example", "*")


async def test_multipart_upload_and_range_get(storage: S3Storage, raw_s3: "S3Client") -> None:
    """녹화 등 대용량 파일 대비 (P13)."""
    key = _key("recordings", "bin")
    part = b"a" * (5 * 1024 * 1024)
    upload = await raw_s3.create_multipart_upload(Bucket=storage.bucket, Key=key)
    upload_id = upload["UploadId"]
    first = await raw_s3.upload_part(
        Bucket=storage.bucket, Key=key, UploadId=upload_id, PartNumber=1, Body=part
    )
    second = await raw_s3.upload_part(
        Bucket=storage.bucket, Key=key, UploadId=upload_id, PartNumber=2, Body=b"b"
    )
    await raw_s3.complete_multipart_upload(
        Bucket=storage.bucket,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={
            "Parts": [
                {"ETag": first["ETag"], "PartNumber": 1},
                {"ETag": second["ETag"], "PartNumber": 2},
            ]
        },
    )

    info = await storage.head(key)
    ranged = await raw_s3.get_object(Bucket=storage.bucket, Key=key, Range="bytes=0-9")

    assert info is not None
    assert info.size == len(part) + 1
    assert ranged["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert await ranged["Body"].read() == b"a" * 10

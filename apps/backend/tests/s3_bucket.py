"""S3 에뮬레이터(floci, 인증 강제) 테스트 버킷 준비.

세션 픽스처 `s3_bucket`(tests/conftest.py)이 쓴다. 세션 시작 때 테스트 전용 버킷을 만들고
(CORS 포함), 끝나면 객체와 버킷을 지운다.
에뮬레이터 주소는 TEST_S3_ENDPOINT_URL(compose·CI가 설정), 없으면 localhost:4566.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

import aioboto3
from aiobotocore.config import AioConfig

from app.core.config import Settings

if TYPE_CHECKING:
    from types_aiobotocore_s3 import S3Client
    from types_aiobotocore_s3.literals import BucketLocationConstraintType

CORS_ORIGIN = "http://localhost:5173"
_CONFIG = AioConfig(signature_version="s3v4", s3={"addressing_style": "path"})


async def _empty_bucket(client: "S3Client", bucket: str) -> None:
    paginator = client.get_paginator("list_objects_v2")
    async for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            await client.delete_object(Bucket=bucket, Key=obj["Key"])


@asynccontextmanager
async def provision_test_bucket(settings: Settings) -> AsyncIterator[str]:
    bucket = settings.s3_bucket
    session = aioboto3.Session(
        aws_access_key_id="test", aws_secret_access_key="test", region_name=settings.aws_region
    )
    async with session.client(
        "s3", endpoint_url=settings.s3_endpoint_url, config=_CONFIG
    ) as client:
        existing = {b["Name"] for b in (await client.list_buckets()).get("Buckets", [])}
        if bucket in existing:
            await _empty_bucket(client, bucket)
        else:
            await client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={
                    "LocationConstraint": cast("BucketLocationConstraintType", settings.aws_region)
                },
            )
        await client.put_bucket_cors(
            Bucket=bucket,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedOrigins": [CORS_ORIGIN],
                        "AllowedMethods": ["GET", "HEAD", "POST", "PUT"],
                        "AllowedHeaders": ["*"],
                        "MaxAgeSeconds": 300,
                    }
                ]
            },
        )
        yield bucket
        await _empty_bucket(client, bucket)
        await client.delete_bucket(Bucket=bucket)

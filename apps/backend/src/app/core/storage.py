"""설정(Settings)으로 S3 어댑터를 만든다."""

from app.core.config import Settings
from app.integrations.s3 import S3Settings, S3Storage


def s3_settings(settings: Settings) -> S3Settings:
    secret = settings.aws_secret_access_key
    return S3Settings(
        bucket=settings.s3_bucket,
        region=settings.aws_region,
        endpoint_url=settings.s3_endpoint_url or None,
        public_endpoint_url=settings.s3_public_endpoint_url or None,
        access_key_id=settings.aws_access_key_id or None,
        secret_access_key=secret.get_secret_value() if secret else None,
        presigned_get_ttl_seconds=settings.s3_presigned_get_ttl_seconds,
        presigned_post_ttl_seconds=settings.s3_presigned_post_ttl_seconds,
    )


def build_s3_storage(settings: Settings) -> S3Storage:
    return S3Storage(s3_settings(settings))

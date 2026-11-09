from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest

from app.core.config import Settings
from app.core.storage import s3_settings
from app.integrations.s3 import S3Settings, S3Storage, content_disposition

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def _storage(public: str | None) -> S3Storage:
    return S3Storage(
        S3Settings(
            bucket="bucket",
            region="ap-northeast-2",
            endpoint_url="http://s3:4566",
            public_endpoint_url=public,
            access_key_id="test",
            secret_access_key="test",
        )
    )


@pytest.mark.parametrize(
    ("public", "host"), [("http://localhost:4566", "localhost:4566"), (None, "s3:4566")]
)
async def test_presigned_urls_are_signed_for_public_endpoint(public: str | None, host: str) -> None:
    """브라우저가 쓸 URL은 공개 주소로 서명한다(서명에 Host 포함). 없으면 서버 주소를 쓴다."""
    storage = _storage(public)

    get_url = await storage.presign_get("contracts/a.pdf")
    post = await storage.presign_post(
        "contracts/a.pdf", content_type="application/pdf", max_bytes=10, now=NOW
    )

    assert urlsplit(get_url).netloc == host
    assert urlsplit(post.url).netloc == host
    assert post.fields["key"] == "contracts/a.pdf"
    assert post.fields["Content-Type"] == "application/pdf"


def test_content_disposition_keeps_non_ascii_name() -> None:
    assert content_disposition('계약 "최종".pdf') == (
        'attachment; filename="?? _??_.pdf"; '
        "filename*=UTF-8''%EA%B3%84%EC%95%BD%20%22%EC%B5%9C%EC%A2%85%22.pdf"
    )


def test_s3_settings_from_app_settings(settings: Settings) -> None:
    config = s3_settings(settings)
    assert config.bucket == settings.s3_bucket
    assert config.access_key_id == "test"
    assert config.secret_access_key == "test"
    assert config.public_endpoint_url == settings.s3_public_endpoint_url

"""S3 어댑터 통합 테스트 픽스처. 테스트 버킷은 tests/conftest.py의 `s3_bucket`."""

import pytest

from app.core.config import Settings
from app.core.storage import build_s3_storage
from app.integrations.s3 import S3Storage


@pytest.fixture
def storage(settings: Settings, s3_bucket: str) -> S3Storage:
    return build_s3_storage(settings)

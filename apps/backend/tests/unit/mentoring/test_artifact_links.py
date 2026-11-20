"""녹화 파일 서명 링크 (A68)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.contexts.mentoring.presentation.artifact_links import (
    LINK_TTL,
    ArtifactGrant,
    ArtifactLinkSigner,
)
from app.core.config import Settings
from app.core.security import JWTService
from app.shared.errors import AuthenticationError
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 20, 3, tzinfo=UTC)


def test_sign_and_verify_bound_to_file_and_user(settings: Settings) -> None:
    signer = ArtifactLinkSigner(settings)
    grant = ArtifactGrant(user_id=new_id(), session_id=new_id(), artifact_id=new_id())
    token, expires_at = signer.sign(grant, now=datetime.now(UTC))
    assert expires_at - datetime.now(UTC) <= LINK_TTL
    assert signer.verify(token, grant.artifact_id) == grant
    with pytest.raises(AuthenticationError) as other:
        signer.verify(token, new_id())  # 다른 파일
    assert other.value.code == "artifact_link_invalid"


def test_expired_forged_and_access_tokens_are_rejected(settings: Settings) -> None:
    signer = ArtifactLinkSigner(settings)
    grant = ArtifactGrant(user_id=new_id(), session_id=new_id(), artifact_id=new_id())
    expired, _ = signer.sign(grant, now=datetime.now(UTC) - LINK_TTL - timedelta(seconds=1))
    access, _ = JWTService(settings).encode(str(grant.user_id), "access", now=datetime.now(UTC))
    for token in (expired, "x.y.z", access, expired[:-2] + "aa"):
        with pytest.raises(AuthenticationError):
            signer.verify(token, grant.artifact_id)

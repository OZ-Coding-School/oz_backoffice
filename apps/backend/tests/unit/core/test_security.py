from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.security import JWTService, hash_password, verify_password
from app.shared.errors import AuthenticationError

pytestmark = pytest.mark.unit


@pytest.fixture
def jwt_service(settings: Settings) -> JWTService:
    return JWTService(settings)


def test_access_token_round_trip(jwt_service: JWTService) -> None:
    now = datetime.now(UTC)
    token, issued = jwt_service.encode("user-1", "access", now=now)

    decoded = jwt_service.decode(token, "access")

    assert decoded.subject == "user-1"
    assert decoded.jti == issued.jti
    assert decoded.expires_at > now


def test_token_type_mismatch_is_rejected(jwt_service: JWTService) -> None:
    token, _ = jwt_service.encode("user-1", "refresh", now=datetime.now(UTC))
    with pytest.raises(AuthenticationError) as exc:
        jwt_service.decode(token, "access")
    assert exc.value.code == "token_invalid"


def test_expired_token_is_rejected(jwt_service: JWTService) -> None:
    long_ago = datetime.now(UTC) - timedelta(days=1)
    token, _ = jwt_service.encode("user-1", "access", now=long_ago)
    with pytest.raises(AuthenticationError) as exc:
        jwt_service.decode(token, "access")
    assert exc.value.code == "token_expired"


def test_tampered_token_is_rejected(jwt_service: JWTService) -> None:
    token, _ = jwt_service.encode("user-1", "access", now=datetime.now(UTC))
    with pytest.raises(AuthenticationError):
        jwt_service.decode(token[:-2] + "xx", "access")


def test_password_hash_and_verify() -> None:
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong", hashed)

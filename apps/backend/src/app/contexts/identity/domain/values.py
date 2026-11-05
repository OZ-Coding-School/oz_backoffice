"""identity 값 정규화·검증 (순수 함수)."""

import re

from app.shared.errors import BusinessRuleViolation

_PHONE_RE = re.compile(r"^01\d{8,9}$")
NAME_MAX_LENGTH = 50


def normalize_phone(raw: str) -> str:
    """휴대폰 번호를 숫자만 남겨 정규화한다. 예: '010-1234-5678' → '01012345678'."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not _PHONE_RE.fullmatch(digits):
        raise BusinessRuleViolation(
            "휴대폰 번호 형식이 올바르지 않습니다.", code="invalid_phone_number"
        )
    return digits


def normalize_name(raw: str) -> str:
    """이름 앞뒤 공백을 제거하고 길이를 검증한다."""
    name = raw.strip()
    if not name or len(name) > NAME_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"이름은 1~{NAME_MAX_LENGTH}자여야 합니다.", code="invalid_name"
        )
    return name

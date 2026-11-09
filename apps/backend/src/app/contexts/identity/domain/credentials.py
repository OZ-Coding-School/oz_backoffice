"""비밀번호 규칙 (decisions A30): 8~64자, 영문·숫자·특수문자를 각각 1개 이상."""

from app.shared.errors import BusinessRuleViolation

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64


def validate_password(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"비밀번호는 {PASSWORD_MIN_LENGTH}~{PASSWORD_MAX_LENGTH}자여야 합니다.",
            code="invalid_password",
        )
    has_letter = any(ch.isascii() and ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    has_special = any(not ch.isalnum() and not ch.isspace() for ch in password)
    if not (has_letter and has_digit and has_special):
        raise BusinessRuleViolation(
            "비밀번호에는 영문, 숫자, 특수문자를 각각 1개 이상 넣어야 합니다.",
            code="invalid_password",
        )

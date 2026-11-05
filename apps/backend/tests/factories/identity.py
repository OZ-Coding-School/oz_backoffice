"""identity 테스트 데이터 빌더."""

from itertools import count
from typing import Any

from app.contexts.identity.domain.entities import User

_seq = count(1)


def make_user(**overrides: Any) -> User:
    n = next(_seq)
    values: dict[str, Any] = {
        "email": f"user{n}@gmail.com",
        "name": f"사용자{n}",
        "phone_number": f"010{n:08d}",
    }
    values.update(overrides)
    return User(**values)

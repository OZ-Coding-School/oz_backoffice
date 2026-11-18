"""identity 테스트 데이터 빌더."""

from itertools import count
from typing import Any

from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import AccountType

_seq = count(1)


def make_user(**overrides: Any) -> User:
    n = next(_seq)
    values: dict[str, Any] = {
        "email": f"user{n}@gmail.com",
        "name": f"사용자{n}",
        "phone_number": f"010{n:08d}",
    }
    values.update(overrides)
    # 회사 도메인이면 운영진, 아니면 수강생 (가입 경로와 같은 기준, A61·A65). 멘토는 직접 넘긴다
    if "account_type" not in values:
        staff = str(values["email"]).endswith("@nextrunners.co.kr")
        values["account_type"] = AccountType.STAFF if staff else AccountType.STUDENT
    return User(**values)

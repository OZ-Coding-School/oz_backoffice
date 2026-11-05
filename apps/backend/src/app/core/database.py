"""Tortoise ORM 설정.

모든 컨텍스트의 모델을 **단일 Tortoise app `models`** 에 등록한다 (decisions B9).
마이그레이션 이력이 하나라서 새 DB에는 `aerich upgrade` 한 번으로 적용된다.
다른 컨텍스트 모델을 FK로 참조할 때는 `fields.ForeignKeyField("models.User")`처럼 쓴다.
컨텍스트 간 코드 경계(다른 컨텍스트 infrastructure import 금지)는 import-linter가 강제한다.
"""

from typing import Any

from app.core.config import get_settings

MODEL_APP = "models"

# 컨텍스트별 모델 모듈 (Tortoise가 모델을 찾는 위치)
MODEL_MODULES: list[str] = [
    "app.contexts.identity.infrastructure.models",
    "app.contexts.access.infrastructure.models",
    "app.contexts.organization.infrastructure.models",
    "app.contexts.academy.infrastructure.models",
    "app.contexts.educator.infrastructure.models",
    "app.contexts.mentoring.infrastructure.models",
    "app.contexts.audit.infrastructure.models",
]


def build_tortoise_config(database_url: str, *, with_aerich: bool = True) -> dict[str, Any]:
    modules = [*MODEL_MODULES, "aerich.models"] if with_aerich else [*MODEL_MODULES]
    return {
        "connections": {"default": database_url},
        "apps": {MODEL_APP: {"models": modules, "default_connection": "default"}},
        "use_tz": True,
        "timezone": "UTC",
    }


# aerich가 읽는 설정 (pyproject.toml [tool.aerich].tortoise_orm)
TORTOISE_ORM = build_tortoise_config(get_settings().database_url)

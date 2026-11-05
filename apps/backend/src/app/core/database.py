"""Tortoise ORM 설정.

컨텍스트마다 Tortoise app을 하나씩 등록한다. 다른 컨텍스트 모델을 FK로 참조할 때는
`fields.ForeignKeyField("academy.Cohort")`처럼 app 이름을 붙인다.
"""

from typing import Any

from app.core.config import get_settings

# Tortoise app 이름 → 모델 모듈
MODEL_MODULES: dict[str, list[str]] = {
    "identity": ["app.contexts.identity.infrastructure.models"],
    "access": ["app.contexts.access.infrastructure.models"],
    "organization": ["app.contexts.organization.infrastructure.models"],
    "academy": ["app.contexts.academy.infrastructure.models"],
    "educator": ["app.contexts.educator.infrastructure.models"],
    "mentoring": ["app.contexts.mentoring.infrastructure.models"],
    "audit": ["app.contexts.audit.infrastructure.models"],
}


def build_tortoise_config(database_url: str, *, with_aerich: bool = True) -> dict[str, Any]:
    apps: dict[str, Any] = {
        name: {"models": modules, "default_connection": "default"}
        for name, modules in MODEL_MODULES.items()
    }
    if with_aerich:
        apps["models"] = {"models": ["aerich.models"], "default_connection": "default"}
    return {
        "connections": {"default": database_url},
        "apps": apps,
        "use_tz": True,
        "timezone": "UTC",
    }


# aerich가 읽는 설정 (pyproject.toml [tool.aerich].tortoise_orm)
TORTOISE_ORM = build_tortoise_config(get_settings().database_url)

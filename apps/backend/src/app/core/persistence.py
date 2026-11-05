"""Tortoise 리포지토리 공통 베이스.

엔티티(dataclass)와 Tortoise 모델의 필드 이름이 같을 때 변환 코드를 줄인다.
FK는 엔티티에서 `<이름>_id` 필드로 두면 모델의 FK 컬럼 속성(`bootcamp_id` 등)과 그대로 대응한다.
필드 이름이 다르거나 하위 엔티티가 있는 애그리거트는 메서드를 오버라이드한다.
"""

import uuid
from typing import Any, ClassVar

from tortoise.models import Model

from app.shared.domain import Entity
from app.shared.errors import NotFoundError


class TortoiseRepository[EntityT: Entity, ModelT: Model]:
    model: ClassVar[type[Model]]
    entity: ClassVar[type[Entity]]
    fields: ClassVar[tuple[str, ...]]

    def to_entity(self, row: ModelT) -> EntityT:
        values = {name: getattr(row, name) for name in self.fields}
        return self.entity(id=row.pk, **values)  # type: ignore[return-value]

    def to_values(self, entity: EntityT) -> dict[str, Any]:
        return {name: getattr(entity, name) for name in self.fields}

    async def add(self, entity: EntityT) -> None:
        await self.model.create(id=entity.id, **self.to_values(entity))

    async def save(self, entity: EntityT) -> None:
        row = await self.model.get_or_none(id=entity.id)
        if row is None:
            raise NotFoundError(f"{self.entity.__name__}을(를) 찾을 수 없습니다.", code="not_found")
        for name, value in self.to_values(entity).items():
            setattr(row, name, value)
        await row.save()  # auto_now(updated_at)가 적용되도록 save()를 쓴다

    async def get(self, entity_id: uuid.UUID) -> EntityT | None:
        row = await self.model.get_or_none(id=entity_id)
        return self.to_entity(row) if row is not None else None  # type: ignore[arg-type]

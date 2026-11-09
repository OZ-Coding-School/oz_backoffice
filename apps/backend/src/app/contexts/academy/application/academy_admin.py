"""학사 마스터 관리 (HRD 과정·회차, 운영과정, 기수). 권한 org.manage (decisions D6).

- 수정은 `dataclasses.replace`로 엔티티를 다시 만들어 생성과 같은 검증(기간 역전 등)을 거친다.
- 기수의 HRD 회차는 운영과정과 같은 HRD 과정의 회차여야 한다 (cohorts note, plan P4).
- 유일 조건은 먼저 검사해 409로 알려 준다: HRD-Net ID, (HRD 과정, 회차 번호),
  운영과정 이름·코드, (운영과정, 기수 번호). 참조 중인 행 삭제는 409 `in_use`.
- 바꿀 수 없는 소속: HRD 회차의 HRD 과정, 운영과정의 HRD 과정, 기수의 운영과정
  (이미 연결된 기수·수강생과의 일관성을 깨지 않기 위해. 필요하면 새로 만든다)
모든 변경은 감사 로그를 남긴다.
"""

import dataclasses
import uuid
from datetime import date
from enum import Enum
from typing import Any

from app.contexts.academy.domain.entities import (
    Bootcamp,
    Cohort,
    HrdNetBootcamp,
    HrdNetBootcampCohort,
)
from app.contexts.academy.domain.repositories import (
    BootcampRepository,
    CohortRepository,
    HrdNetBootcampCohortRepository,
    HrdNetBootcampRepository,
)
from app.contexts.audit.application.recorder import AuditRecorder
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, ConflictError, NotFoundError

Master = HrdNetBootcamp | HrdNetBootcampCohort | Bootcamp | Cohort

# 수정할 수 있는 필드 (소속 FK는 바꾸지 않는다)
HRD_BOOTCAMP_FIELDS = frozenset(
    {
        "name",
        "hrd_net_id",
        "train_type",
        "ncs1_se",
        "ncs2_se",
        "ncs3_se",
        "weekend_se",
        "day_night_se",
        "total_train_fee",
        "train_fee_per_hour",
        "total_train_hours",
        "total_train_days",
    }
)
HRD_COHORT_FIELDS = frozenset(
    {"cohort_number", "train_start_date", "train_end_date", "self_pay_amount"}
)
BOOTCAMP_FIELDS = frozenset({"name", "code", "is_active"})
COHORT_FIELDS = frozenset(
    {"hrd_net_cohort_id", "cohort_number", "start_date", "end_date", "status", "discord_guild_id"}
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID | date):
        return str(value) if isinstance(value, uuid.UUID) else value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _snapshot(entity: Master) -> dict[str, Any]:
    return {
        f.name: _jsonable(getattr(entity, f.name))
        for f in dataclasses.fields(entity)
        if f.init and f.name != "id"
    }


class AcademyAdminService:
    def __init__(
        self,
        *,
        hrd_bootcamps: HrdNetBootcampRepository,
        hrd_cohorts: HrdNetBootcampCohortRepository,
        bootcamps: BootcampRepository,
        cohorts: CohortRepository,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._hrd_bootcamps = hrd_bootcamps
        self._hrd_cohorts = hrd_cohorts
        self._bootcamps = bootcamps
        self._cohorts = cohorts
        self._audit = audit
        self._uow = uow

    # ------------------------------------------------------------------ HRD 과정
    async def list_hrd_bootcamps(self) -> list[HrdNetBootcamp]:
        return await self._hrd_bootcamps.list_all()

    async def get_hrd_bootcamp(self, entity_id: uuid.UUID) -> HrdNetBootcamp:
        return _found(await self._hrd_bootcamps.get(entity_id), "hrd_bootcamp_not_found")

    async def create_hrd_bootcamp(
        self, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> HrdNetBootcamp:
        bootcamp = HrdNetBootcamp(**values)
        async with self._uow:
            await self._ensure_hrd_net_id_free(bootcamp.hrd_net_id)
            await self._hrd_bootcamps.add(bootcamp)
            await self._record(actor_id, "hrd_bootcamp.create", bootcamp)
        return bootcamp

    async def update_hrd_bootcamp(
        self, entity_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> HrdNetBootcamp:
        _allowed(changes, HRD_BOOTCAMP_FIELDS)
        async with self._uow:
            current = await self.get_hrd_bootcamp(entity_id)
            updated = dataclasses.replace(current, **changes)
            if updated.hrd_net_id != current.hrd_net_id:
                await self._ensure_hrd_net_id_free(updated.hrd_net_id)
            await self._hrd_bootcamps.save(updated)
            await self._record(actor_id, "hrd_bootcamp.update", updated, before=current)
        return updated

    async def delete_hrd_bootcamp(self, entity_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            current = await self.get_hrd_bootcamp(entity_id)
            await self._hrd_bootcamps.delete(entity_id)
            await self._record(actor_id, "hrd_bootcamp.delete", current, deleted=True)

    # ------------------------------------------------------------------ HRD 회차
    async def list_hrd_cohorts(self, hrd_bootcamp_id: uuid.UUID) -> list[HrdNetBootcampCohort]:
        await self.get_hrd_bootcamp(hrd_bootcamp_id)
        return await self._hrd_cohorts.list_by_bootcamp(hrd_bootcamp_id)

    async def get_hrd_cohort(self, entity_id: uuid.UUID) -> HrdNetBootcampCohort:
        return _found(await self._hrd_cohorts.get(entity_id), "hrd_cohort_not_found")

    async def create_hrd_cohort(
        self, hrd_bootcamp_id: uuid.UUID, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> HrdNetBootcampCohort:
        cohort = HrdNetBootcampCohort(hrd_net_bootcamp_id=hrd_bootcamp_id, **values)
        async with self._uow:
            await self.get_hrd_bootcamp(hrd_bootcamp_id)
            await self._ensure_hrd_cohort_number_free(hrd_bootcamp_id, cohort.cohort_number)
            await self._hrd_cohorts.add(cohort)
            await self._record(actor_id, "hrd_cohort.create", cohort)
        return cohort

    async def update_hrd_cohort(
        self, entity_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> HrdNetBootcampCohort:
        _allowed(changes, HRD_COHORT_FIELDS)
        async with self._uow:
            current = await self.get_hrd_cohort(entity_id)
            updated = dataclasses.replace(current, **changes)
            if updated.cohort_number != current.cohort_number:
                await self._ensure_hrd_cohort_number_free(
                    updated.hrd_net_bootcamp_id, updated.cohort_number
                )
            await self._hrd_cohorts.save(updated)
            await self._record(actor_id, "hrd_cohort.update", updated, before=current)
        return updated

    async def delete_hrd_cohort(self, entity_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            current = await self.get_hrd_cohort(entity_id)
            await self._hrd_cohorts.delete(entity_id)
            await self._record(actor_id, "hrd_cohort.delete", current, deleted=True)

    # ------------------------------------------------------------------ 운영과정
    async def list_bootcamps(self, *, include_inactive: bool) -> list[Bootcamp]:
        if include_inactive:
            return await self._bootcamps.list_all()
        return await self._bootcamps.list_active()

    async def get_bootcamp(self, entity_id: uuid.UUID) -> Bootcamp:
        return _found(await self._bootcamps.get(entity_id), "bootcamp_not_found")

    async def create_bootcamp(self, values: dict[str, Any], *, actor_id: uuid.UUID) -> Bootcamp:
        bootcamp = Bootcamp(**values)
        async with self._uow:
            await self.get_hrd_bootcamp(bootcamp.hrd_net_bootcamp_id)
            await self._ensure_bootcamp_unique(bootcamp)
            await self._bootcamps.add(bootcamp)
            await self._record(actor_id, "bootcamp.create", bootcamp)
        return bootcamp

    async def update_bootcamp(
        self, entity_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> Bootcamp:
        _allowed(changes, BOOTCAMP_FIELDS)
        async with self._uow:
            current = await self.get_bootcamp(entity_id)
            updated = dataclasses.replace(current, **changes)
            await self._ensure_bootcamp_unique(updated, exclude=current.id)
            await self._bootcamps.save(updated)
            await self._record(actor_id, "bootcamp.update", updated, before=current)
        return updated

    async def delete_bootcamp(self, entity_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """기수·담당자가 있으면 409 in_use. 운영을 멈출 때는 is_active=false로 비활성화한다."""
        async with self._uow:
            current = await self.get_bootcamp(entity_id)
            await self._bootcamps.delete(entity_id)
            await self._record(actor_id, "bootcamp.delete", current, deleted=True)

    # ------------------------------------------------------------------ 기수
    async def list_cohorts(self, bootcamp_id: uuid.UUID) -> list[Cohort]:
        await self.get_bootcamp(bootcamp_id)
        return await self._cohorts.list_by_bootcamp(bootcamp_id)

    async def get_cohort(self, entity_id: uuid.UUID) -> Cohort:
        return _found(await self._cohorts.get(entity_id), "cohort_not_found")

    async def create_cohort(
        self, bootcamp_id: uuid.UUID, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> Cohort:
        cohort = Cohort(bootcamp_id=bootcamp_id, **values)
        async with self._uow:
            bootcamp = await self.get_bootcamp(bootcamp_id)
            await self._ensure_same_hrd_bootcamp(bootcamp, cohort.hrd_net_cohort_id)
            await self._ensure_cohort_number_free(bootcamp_id, cohort.cohort_number)
            await self._cohorts.add(cohort)
            await self._record(actor_id, "cohort.create", cohort)
        return cohort

    async def update_cohort(
        self, entity_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> Cohort:
        _allowed(changes, COHORT_FIELDS)
        async with self._uow:
            current = await self.get_cohort(entity_id)
            updated = dataclasses.replace(current, **changes)
            if updated.hrd_net_cohort_id != current.hrd_net_cohort_id:
                bootcamp = await self.get_bootcamp(updated.bootcamp_id)
                await self._ensure_same_hrd_bootcamp(bootcamp, updated.hrd_net_cohort_id)
            if updated.cohort_number != current.cohort_number:
                await self._ensure_cohort_number_free(updated.bootcamp_id, updated.cohort_number)
            await self._cohorts.save(updated)
            await self._record(actor_id, "cohort.update", updated, before=current)
        return updated

    async def delete_cohort(self, entity_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """수강생·담당자가 있으면 409 in_use. 운영이 끝나면 상태를 ENDED·ARCHIVED로 바꾼다."""
        async with self._uow:
            current = await self.get_cohort(entity_id)
            await self._cohorts.delete(entity_id)
            await self._record(actor_id, "cohort.delete", current, deleted=True)

    # ------------------------------------------------------------------ 검증
    async def _ensure_hrd_net_id_free(self, hrd_net_id: str | None) -> None:
        if hrd_net_id and await self._hrd_bootcamps.get_by_hrd_net_id(hrd_net_id):
            raise ConflictError("같은 HRD-Net ID가 있습니다.", code="hrd_net_id_taken")

    async def _ensure_hrd_cohort_number_free(self, hrd_bootcamp_id: uuid.UUID, number: int) -> None:
        if await self._hrd_cohorts.get_by_number(hrd_bootcamp_id, number):
            raise ConflictError("같은 HRD 회차 번호가 있습니다.", code="hrd_cohort_number_taken")

    async def _ensure_bootcamp_unique(
        self, bootcamp: Bootcamp, *, exclude: uuid.UUID | None = None
    ) -> None:
        by_name = await self._bootcamps.get_by_name(bootcamp.name)
        if by_name is not None and by_name.id != exclude:
            raise ConflictError("같은 이름의 운영과정이 있습니다.", code="bootcamp_name_taken")
        by_code = await self._bootcamps.get_by_code(bootcamp.code)
        if by_code is not None and by_code.id != exclude:
            raise ConflictError("같은 코드의 운영과정이 있습니다.", code="bootcamp_code_taken")

    async def _ensure_cohort_number_free(self, bootcamp_id: uuid.UUID, number: int) -> None:
        if await self._cohorts.get_by_number(bootcamp_id, number):
            raise ConflictError("같은 기수 번호가 있습니다.", code="cohort_number_taken")

    async def _ensure_same_hrd_bootcamp(self, bootcamp: Bootcamp, hrd_cohort_id: uuid.UUID) -> None:
        hrd_cohort = await self.get_hrd_cohort(hrd_cohort_id)
        if hrd_cohort.hrd_net_bootcamp_id != bootcamp.hrd_net_bootcamp_id:
            raise BusinessRuleViolation(
                "운영과정과 다른 HRD 과정의 회차는 연결할 수 없습니다.",
                code="hrd_cohort_mismatch",
            )

    async def _record(
        self,
        actor_id: uuid.UUID,
        action: str,
        entity: Master,
        *,
        before: Master | None = None,
        deleted: bool = False,
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"academy.{action}",
            target_type=action.split(".", 1)[0],
            target_id=entity.id,
            before=_snapshot(before or entity) if before or deleted else None,
            after=None if deleted else _snapshot(entity),
        )


def _found[T](entity: T | None, code: str) -> T:
    if entity is None:
        raise NotFoundError("대상을 찾을 수 없습니다.", code=code)
    return entity


def _allowed(changes: dict[str, Any], fields: frozenset[str]) -> None:
    unknown = set(changes) - fields
    if unknown:
        raise BusinessRuleViolation(
            f"바꿀 수 없는 항목입니다: {', '.join(sorted(unknown))}", code="field_not_updatable"
        )

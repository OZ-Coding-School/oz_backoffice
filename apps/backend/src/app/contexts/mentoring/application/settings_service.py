"""기수 멘토링 설정·금지 시간대·추가 휴일 관리 (decisions A34, 권한 mentoring.settings.manage).

- 설정은 첫 저장 때 만든다. 없는 기수를 조회하면 404 `mentoring_settings_not_configured`
  (프론트가 설정 페이지로 안내).
- 금지 시간대는 같은 기수에서 기간·시간대가 모두 겹치면 409.
  수정·삭제는 언제든 하고 소급하지 않는다.
- 추가 휴일은 전사 공통(날짜당 하나).
모든 변경은 감사 로그를 남긴다.
"""

import dataclasses
import uuid
from datetime import date, time
from enum import Enum
from typing import Any, Protocol

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.mentoring.domain.repositories import (
    CohortMentoringSettingsRepository,
    MentoringBlockTimeRepository,
    MentoringHolidayRepository,
)
from app.contexts.mentoring.domain.settings import (
    CohortMentoringSettings,
    MentoringBlockTime,
    MentoringHoliday,
)
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError, NotFoundError


class CohortDirectory(Protocol):
    """academy `AcademyCatalog`."""

    async def bootcamp_id_of(self, cohort_id: uuid.UUID) -> uuid.UUID | None: ...


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date | time):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _snapshot(entity: Any) -> dict[str, Any]:
    skip = {"id", "created_at", "updated_at"}
    return {
        f.name: _jsonable(getattr(entity, f.name))
        for f in dataclasses.fields(entity)
        if f.init and f.name not in skip
    }


class MentoringSettingsService:
    def __init__(
        self,
        *,
        settings: CohortMentoringSettingsRepository,
        blocks: MentoringBlockTimeRepository,
        holidays: MentoringHolidayRepository,
        cohorts: CohortDirectory,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._settings = settings
        self._blocks = blocks
        self._holidays = holidays
        self._cohorts = cohorts
        self._audit = audit
        self._uow = uow

    # ------------------------------------------------------------------ 설정
    async def get_settings(self, cohort_id: uuid.UUID) -> CohortMentoringSettings:
        await self._ensure_cohort(cohort_id)
        current = await self._settings.get_by_cohort(cohort_id)
        if current is None:
            raise NotFoundError(
                "이 기수의 멘토링 설정이 아직 없습니다. 먼저 설정을 저장하세요.",
                code="mentoring_settings_not_configured",
            )
        return current

    async def save_settings(
        self, cohort_id: uuid.UUID, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> CohortMentoringSettings:
        """설정 전체를 저장한다(없으면 만든다). 진행 중인 신청에는 소급하지 않는다."""
        await self._ensure_cohort(cohort_id)
        async with self._uow:
            current = await self._settings.get_by_cohort(cohort_id)
            if current is None:
                saved = CohortMentoringSettings(cohort_id=cohort_id, **values)
                await self._settings.add(saved)
                await self._record(actor_id, "settings.create", saved, None)
            else:
                saved = current.changed(values)
                await self._settings.save(saved)
                await self._record(actor_id, "settings.update", saved, current)
        return await self.get_settings(cohort_id)

    # ------------------------------------------------------------------ 금지 시간대
    async def list_blocks(self, cohort_id: uuid.UUID) -> list[MentoringBlockTime]:
        await self._ensure_cohort(cohort_id)
        return await self._blocks.list_by_cohort(cohort_id)

    async def create_block(
        self, cohort_id: uuid.UUID, values: dict[str, Any], *, actor_id: uuid.UUID
    ) -> MentoringBlockTime:
        await self._ensure_cohort(cohort_id)
        block = MentoringBlockTime(cohort_id=cohort_id, **values)
        async with self._uow:
            await self._ensure_no_overlap(block)
            await self._blocks.add(block)
            await self._record(actor_id, "block_time.create", block, None)
        return block

    async def update_block(
        self,
        cohort_id: uuid.UUID,
        block_id: uuid.UUID,
        values: dict[str, Any],
        *,
        actor_id: uuid.UUID,
    ) -> MentoringBlockTime:
        async with self._uow:
            current = await self._block_of(cohort_id, block_id)
            updated = current.revised(values)
            await self._ensure_no_overlap(updated)
            await self._blocks.save(updated)
            await self._record(actor_id, "block_time.update", updated, current)
        return updated

    async def delete_block(
        self, cohort_id: uuid.UUID, block_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> None:
        async with self._uow:
            current = await self._block_of(cohort_id, block_id)
            await self._blocks.delete(block_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.block_time.delete",
                target_type="mentoring_block_time",
                target_id=block_id,
                before=_snapshot(current),
            )

    # ------------------------------------------------------------------ 추가 휴일
    async def create_holiday(
        self, holiday_date: date, name: str, *, actor_id: uuid.UUID
    ) -> MentoringHoliday:
        holiday = MentoringHoliday(holiday_date=holiday_date, name=name)
        async with self._uow:
            if await self._holidays.get_by_date(holiday_date) is not None:
                raise ConflictError("이미 등록된 휴일입니다.", code="holiday_already_exists")
            await self._holidays.add(holiday)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.holiday.create",
                target_type="mentoring_holiday",
                target_id=holiday.id,
                after=_snapshot(holiday),
            )
        return holiday

    async def delete_holiday(self, holiday_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        async with self._uow:
            holiday = await self._holidays.get(holiday_id)
            if holiday is None:
                raise NotFoundError("휴일을 찾을 수 없습니다.", code="holiday_not_found")
            await self._holidays.delete(holiday_id)
            await self._audit.record(
                actor_user_id=actor_id,
                action="mentoring.holiday.delete",
                target_type="mentoring_holiday",
                target_id=holiday_id,
                before=_snapshot(holiday),
            )

    # ------------------------------------------------------------------ 내부
    async def _ensure_cohort(self, cohort_id: uuid.UUID) -> None:
        if await self._cohorts.bootcamp_id_of(cohort_id) is None:
            raise NotFoundError("기수를 찾을 수 없습니다.", code="cohort_not_found")

    async def _block_of(self, cohort_id: uuid.UUID, block_id: uuid.UUID) -> MentoringBlockTime:
        block = await self._blocks.get(block_id)
        if block is None or block.cohort_id != cohort_id:
            raise NotFoundError("금지 시간대를 찾을 수 없습니다.", code="block_time_not_found")
        return block

    async def _ensure_no_overlap(self, block: MentoringBlockTime) -> None:
        for other in await self._blocks.list_by_cohort(block.cohort_id):
            if other.id != block.id and other.overlaps(block):
                raise ConflictError(
                    "같은 기수에 기간과 시간대가 겹치는 금지 시간대가 있습니다.",
                    code="block_time_overlap",
                )

    async def _record(
        self, actor_id: uuid.UUID, action: str, entity: Any, before: Any | None
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"mentoring.{action}",
            target_type="mentoring_settings"
            if action.startswith("settings")
            else "mentoring_block_time",
            target_id=entity.id,
            before=_snapshot(before) if before is not None else None,
            after=_snapshot(entity),
        )

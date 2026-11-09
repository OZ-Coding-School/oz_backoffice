"""educator 리포지토리 구현 (Tortoise)."""

import uuid
from datetime import date

from tortoise.expressions import Q

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.models import ContractFileModel, EducatorContractModel
from app.core.persistence import TortoiseRepository


class TortoiseContractFileRepository(TortoiseRepository[ContractFile, ContractFileModel]):
    model = ContractFileModel
    entity = ContractFile
    fields = ("file_name", "file_ext", "file_size", "storage_key", "deleted_at")

    def to_entity(self, row: ContractFileModel) -> ContractFile:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        return entity

    async def list_by_ids(self, file_ids: list[uuid.UUID]) -> list[ContractFile]:
        if not file_ids:
            return []
        rows = await ContractFileModel.filter(id__in=file_ids)
        return [self.to_entity(row) for row in rows]


class TortoiseEducatorContractRepository(
    TortoiseRepository[EducatorContract, EducatorContractModel]
):
    model = EducatorContractModel
    entity = EducatorContract
    fields = (
        "manager_employee_id",
        "educator_type",
        "contractor_name",
        "contractor_phone",
        "title",
        "start_date",
        "end_date",
        "contractor_email",
        "contract_file_id",
        "mentor_id",
        "instructor_id",
        "status",
    )

    def to_entity(self, row: EducatorContractModel) -> EducatorContract:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    async def get_by_file(self, file_id: uuid.UUID) -> EducatorContract | None:
        row = await EducatorContractModel.get_or_none(contract_file_id=file_id)
        return self.to_entity(row) if row else None

    async def list_page(
        self, contract_filter: ContractFilter, *, limit: int, offset: int
    ) -> tuple[list[EducatorContract], int]:
        query = EducatorContractModel.all()
        if contract_filter.statuses:
            query = query.filter(status__in=list(contract_filter.statuses))
        if contract_filter.educator_type is not None:
            query = query.filter(educator_type=contract_filter.educator_type)
        if contract_filter.query:
            query = query.filter(_search(contract_filter.query))
        total = await query.count()
        rows = await query.order_by("-created_at", "-id").offset(offset).limit(limit)
        return [self.to_entity(row) for row in rows], total

    async def list_active_ended_before(self, today: date) -> list[EducatorContract]:
        rows = await EducatorContractModel.filter(
            status=ContractStatus.ACTIVE, end_date__lt=today
        ).order_by("end_date", "id")
        return [self.to_entity(row) for row in rows]


def _search(text: str) -> Q:
    term = text.strip()
    condition = Q(contractor_name__icontains=term) | Q(title__icontains=term)
    digits = "".join(ch for ch in term if ch.isdigit())
    if digits:
        condition |= Q(contractor_phone__contains=digits)
    return condition

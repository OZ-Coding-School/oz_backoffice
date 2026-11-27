"""educator 리포지토리 구현 (Tortoise)."""

import re
import uuid
from datetime import date
from typing import cast

from tortoise.expressions import Q
from tortoise.functions import Count
from tortoise.queryset import QuerySet

from app.contexts.educator.domain.entities import (
    ContractAmendment,
    ContractFile,
    EducatorContract,
)
from app.contexts.educator.domain.enums import ContractStatus, ContractType
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import ContractFilter
from app.contexts.educator.infrastructure.models import (
    ContractAmendmentModel,
    ContractFileModel,
    EducatorContractModel,
    InstructorModel,
    MentorModel,
)
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
        "contract_type",
        "bootcamp_id",
        "cohort_id",
        "contractor_name",
        "contractor_phone",
        "contractor_email",
        "business_registration_number",
        "contact_person_name",
        "title",
        "start_date",
        "end_date",
        "settlement_type",
        "total_amount",
        "unit_price",
        "price_unit",
        "vat_type",
        "amount_note",
        "no_show_pay_amount",
        "mentoring_time_basis",
        "contract_file_id",
        "mentor_id",
        "instructor_id",
        "status",
        "cancel_reason",
        "canceled_on",
        "termination_reason",
        "termination_detail",
        "terminated_on",
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
        query = _filtered(contract_filter, with_types=True)
        if query is None:
            return [], 0
        total = await query.count()
        rows = await query.order_by("-created_at", "-id").offset(offset).limit(limit)
        return [self.to_entity(row) for row in rows], total

    async def count_by_types(self, contract_filter: ContractFilter) -> dict[ContractType, int]:
        counts = dict.fromkeys(ContractType, 0)
        query = _filtered(contract_filter, with_types=False)
        if query is None:
            return counts
        rows = (
            await query.annotate(n=Count("id"))
            .group_by("contract_type")
            .values("contract_type", "n")
        )
        for row in rows:
            counts[ContractType(row["contract_type"])] = row["n"]
        return counts

    async def list_by_ids(self, contract_ids: list[uuid.UUID]) -> list[EducatorContract]:
        if not contract_ids:
            return []
        rows = await EducatorContractModel.filter(id__in=contract_ids)
        return [self.to_entity(row) for row in rows]

    async def list_mentor_contracts(self, mentor_id: uuid.UUID) -> list[EducatorContract]:
        rows = await EducatorContractModel.filter(
            mentor_id=mentor_id, contract_type=ContractType.MENTOR
        ).order_by("-created_at", "-id")
        return [self.to_entity(row) for row in rows]

    async def list_due(self, today: date) -> list[EducatorContract]:
        rows = await EducatorContractModel.filter(
            Q(status=ContractStatus.SIGNED, start_date__isnull=True)
            | Q(status=ContractStatus.SIGNED, start_date__lte=today)
            | Q(status=ContractStatus.ACTIVE, end_date__lt=today)
        ).order_by("created_at", "id")
        return [self.to_entity(row) for row in rows]

    async def search_unlinked_mentor_contracts(
        self, *, name: str, phone_number: str | None, query: str | None, limit: int
    ) -> list[EducatorContract]:
        rows = EducatorContractModel.filter(
            contract_type=ContractType.MENTOR, mentor_id__isnull=True
        )
        if query:
            cond = Q(contractor_name__icontains=query)
            digits = re.sub(r"\D", "", query)
            if len(digits) >= 3:
                cond |= Q(contractor_phone__contains=digits)
        else:
            cond = Q(contractor_name=name)
            if phone_number:
                cond |= Q(contractor_phone=phone_number)
        found = await rows.filter(cond).order_by("contractor_name", "-created_at").limit(limit)
        return [self.to_entity(row) for row in found]

    async def find_unlinked_mentor_contracts(
        self, contractor_name: str, contractor_phone: str
    ) -> list[EducatorContract]:
        # (contractor_name, contractor_phone) 인덱스를 쓴다
        rows = await EducatorContractModel.filter(
            contractor_name=contractor_name,
            contractor_phone=contractor_phone,
            contract_type=ContractType.MENTOR,
            mentor_id__isnull=True,
        ).order_by("created_at", "id")
        return [self.to_entity(row) for row in rows]

    async def count_by_mentors(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not mentor_ids:
            return {}
        rows = (
            await EducatorContractModel.filter(mentor_id__in=mentor_ids)
            .annotate(count=Count("id"))
            .group_by("mentor_id")
            .values("mentor_id", "count")
        )
        return {row["mentor_id"]: row["count"] for row in rows}


class TortoiseContractAmendmentRepository(
    TortoiseRepository[ContractAmendment, ContractAmendmentModel]
):
    model = ContractAmendmentModel
    entity = ContractAmendment
    fields = (
        "contract_id",
        "amended_on",
        "reason",
        "before",
        "after",
        "created_by_user_id",
        "contract_file_id",
    )

    def to_entity(self, row: ContractAmendmentModel) -> ContractAmendment:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        return entity

    async def list_by_contract(self, contract_id: uuid.UUID) -> list[ContractAmendment]:
        rows = await ContractAmendmentModel.filter(contract_id=contract_id).order_by(
            "-created_at", "-id"
        )
        return [self.to_entity(row) for row in rows]

    async def file_in_use(self, file_id: uuid.UUID) -> bool:
        return await ContractAmendmentModel.filter(contract_file_id=file_id).exists()


class TortoiseMentorRepository(TortoiseRepository[Mentor, MentorModel]):
    model = MentorModel
    entity = Mentor
    fields = (
        "user_id",
        "contact_name",
        "contact_phone",
        "nickname",
        "display_name_preference",
        "headline",
        "introduction",
        "expertise",
        "profile_image_key",
        "is_active",
        "accepting_requests",
    )

    def to_entity(self, row: MentorModel) -> Mentor:
        entity = super().to_entity(row)
        entity.created_at = row.created_at
        entity.updated_at = row.updated_at
        return entity

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None:
        row = await MentorModel.get_or_none(user_id=user_id)
        return self.to_entity(row) if row else None

    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]:
        if not mentor_ids:
            return {}
        rows = await MentorModel.filter(id__in=mentor_ids)
        return {row.id: self.to_entity(row) for row in rows}

    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None:
        row = await MentorModel.select_for_update().get_or_none(id=mentor_id)
        return self.to_entity(row) if row else None

    async def delete(self, mentor_id: uuid.UUID) -> None:
        await MentorModel.filter(id=mentor_id).delete()

    async def find_same_person(self, name: str, phone: str) -> list[Mentor]:
        rows = await MentorModel.filter(
            Q(user__name=name, user__phone_number=phone)
            | Q(user_id__isnull=True, contact_name=name, contact_phone=phone)
        ).order_by("created_at", "id")
        return [self.to_entity(row) for row in rows]

    async def search_pending(
        self, *, name: str, phone: str | None, query: str | None, limit: int
    ) -> list[Mentor]:
        rows = MentorModel.filter(user_id__isnull=True)
        if query:
            cond = Q(contact_name__icontains=query)
            digits = re.sub(r"\D", "", query)
            if len(digits) >= 3:
                cond |= Q(contact_phone__contains=digits)
        else:
            cond = Q(contact_name=name)
            if phone:
                cond |= Q(contact_phone=phone)
        found = await rows.filter(cond).order_by("contact_name", "id").limit(limit)
        return [self.to_entity(row) for row in found]

    async def list_page(
        self,
        *,
        query: str | None,
        is_active: bool | None,
        limit: int,
        offset: int,
        registered: bool | None = None,
    ) -> tuple[list[Mentor], int]:
        rows_query = MentorModel.all()
        if is_active is not None:
            rows_query = rows_query.filter(is_active=is_active)
        if registered is not None:
            rows_query = rows_query.filter(user_id__isnull=not registered)
        if query:
            # 회원 정보는 FK 관계(users)로 조인해 찾는다 (identity 코드는 import하지 않는다)
            term = query.strip()
            condition = (
                Q(nickname__icontains=term)
                | Q(user__name__icontains=term)
                | Q(user__email__icontains=term)
                | Q(contact_name__icontains=term)
            )
            digits = "".join(ch for ch in term if ch.isdigit())
            if digits:
                condition |= Q(user__phone_number__contains=digits) | Q(
                    contact_phone__contains=digits
                )
            rows_query = rows_query.filter(condition)
        total = await rows_query.count()
        rows = await rows_query.order_by("-created_at", "-id").offset(offset).limit(limit)
        return [self.to_entity(row) for row in rows], total


class TortoiseInstructorRepository:
    async def exists(self, instructor_id: uuid.UUID) -> bool:
        return await InstructorModel.exists(id=instructor_id)

    async def user_ids(self, instructor_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        """강사 id → 회원 id"""
        if not instructor_ids:
            return {}
        rows = await InstructorModel.filter(id__in=instructor_ids).values_list("id", "user_id")
        return {cast("uuid.UUID", i): cast("uuid.UUID", u) for i, u in rows}


def _search(text: str) -> Q:
    term = text.strip()
    condition = Q(contractor_name__icontains=term) | Q(title__icontains=term)
    digits = "".join(ch for ch in term if ch.isdigit())
    if digits:
        condition |= Q(contractor_phone__contains=digits)
    return condition


def _filtered(
    contract_filter: ContractFilter, *, with_types: bool
) -> "QuerySet[EducatorContractModel] | None":
    """목록 조건을 건 쿼리. 담당 범위가 비어 있으면 None (보이는 계약이 없음)."""
    query = EducatorContractModel.all()
    if contract_filter.statuses:
        query = query.filter(status__in=list(contract_filter.statuses))
    if with_types and contract_filter.contract_types:
        query = query.filter(contract_type__in=list(contract_filter.contract_types))
    if contract_filter.bootcamp_id is not None:
        query = query.filter(bootcamp_id=contract_filter.bootcamp_id)
    if contract_filter.cohort_id is not None:
        if contract_filter.common_bootcamp_id is not None:
            # 그 기수의 계약 + 같은 과정의 과정 공통 계약 (A112)
            query = query.filter(
                Q(cohort_id=contract_filter.cohort_id)
                | Q(cohort_id__isnull=True, bootcamp_id=contract_filter.common_bootcamp_id)
            )
        else:
            query = query.filter(cohort_id=contract_filter.cohort_id)
    if contract_filter.visible is not None:
        visible = contract_filter.visible
        if not (visible.bootcamp_ids or visible.cohort_ids):
            return None
        query = query.filter(
            Q(bootcamp_id__in=list(visible.bootcamp_ids))
            | Q(cohort_id__in=list(visible.cohort_ids))
        )
    if contract_filter.query:
        query = query.filter(_search(contract_filter.query))
    if contract_filter.mentor_id is not None:
        query = query.filter(mentor_id=contract_filter.mentor_id)
    return query

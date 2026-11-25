"""educator 인메모리 리포지토리와 가짜 파일 저장소·직원 조회."""

import dataclasses
import uuid
from datetime import date, datetime, timedelta

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus, EducatorType
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.domain.repositories import ContractFilter
from app.integrations.s3 import ObjectInfo, PresignedPost

POST_TTL = timedelta(minutes=10)


class InMemoryContractRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, EducatorContract] = {}

    async def add(self, contract: EducatorContract) -> None:
        self.items[contract.id] = dataclasses.replace(contract)

    async def save(self, contract: EducatorContract) -> None:
        self.items[contract.id] = dataclasses.replace(contract)

    async def delete(self, contract_id: uuid.UUID) -> None:
        self.items.pop(contract_id, None)

    async def get(self, contract_id: uuid.UUID) -> EducatorContract | None:
        found = self.items.get(contract_id)
        return dataclasses.replace(found) if found else None

    async def get_by_file(self, file_id: uuid.UUID) -> EducatorContract | None:
        return next((c for c in self.items.values() if c.contract_file_id == file_id), None)

    async def list_page(
        self, contract_filter: ContractFilter, *, limit: int, offset: int
    ) -> tuple[list[EducatorContract], int]:
        matched = [
            c
            for c in self.items.values()
            if (not contract_filter.statuses or c.status in contract_filter.statuses)
            and (contract_filter.mentor_id is None or c.mentor_id == contract_filter.mentor_id)
        ]
        return matched[offset : offset + limit], len(matched)

    async def list_active_ended_before(self, today: date) -> list[EducatorContract]:
        return [
            dataclasses.replace(c)
            for c in self.items.values()
            if c.status is ContractStatus.ACTIVE and c.end_date < today
        ]

    async def search_unlinked_mentor_contracts(
        self, *, name: str, phone_number: str | None, query: str | None, limit: int
    ) -> list[EducatorContract]:
        def hit(c: EducatorContract) -> bool:
            if query:
                return query in c.contractor_name or (
                    len(query) >= 3 and query in (c.contractor_phone or "")
                )
            return c.contractor_name == name or (
                phone_number is not None and c.contractor_phone == phone_number
            )

        return [
            dataclasses.replace(c)
            for c in self.items.values()
            if c.educator_type is EducatorType.MENTOR and c.mentor_id is None and hit(c)
        ][:limit]

    async def find_unlinked_mentor_contracts(
        self, contractor_name: str, contractor_phone: str
    ) -> list[EducatorContract]:
        return [
            dataclasses.replace(c)
            for c in self.items.values()
            if c.contractor_name == contractor_name
            and c.contractor_phone == contractor_phone
            and c.educator_type is EducatorType.MENTOR
            and c.mentor_id is None
        ]

    async def count_by_mentors(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        counts: dict[uuid.UUID, int] = {}
        for c in self.items.values():
            if c.mentor_id in mentor_ids:
                counts[c.mentor_id] = counts.get(c.mentor_id, 0) + 1
        return counts


class InMemoryMentorRepository:
    def __init__(self, *mentors: Mentor) -> None:
        self.items = {m.id: m for m in mentors}

    async def add(self, mentor: Mentor) -> None:
        self.items[mentor.id] = dataclasses.replace(mentor)

    async def get(self, mentor_id: uuid.UUID) -> Mentor | None:
        found = self.items.get(mentor_id)
        return dataclasses.replace(found) if found else None

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor | None:
        found = next((m for m in self.items.values() if m.user_id == user_id), None)
        return dataclasses.replace(found) if found else None

    async def get_many(self, mentor_ids: list[uuid.UUID]) -> dict[uuid.UUID, Mentor]:
        return {i: dataclasses.replace(self.items[i]) for i in mentor_ids if i in self.items}

    async def lock(self, mentor_id: uuid.UUID) -> Mentor | None:
        return await self.get(mentor_id)

    async def save(self, mentor: Mentor) -> None:
        self.items[mentor.id] = dataclasses.replace(mentor)

    async def delete(self, mentor_id: uuid.UUID) -> None:
        self.items.pop(mentor_id, None)

    async def find_same_person(self, name: str, phone: str) -> list[Mentor]:
        """가입 전 멘토만 연락처로 찾는다 (회원 정보는 인메모리에 없다)"""
        return [
            m
            for m in self.items.values()
            if m.user_id is None and (m.contact_name, m.contact_phone) == (name, phone)
        ]

    async def search_pending(
        self, *, name: str, phone: str | None, query: str | None, limit: int
    ) -> list[Mentor]:
        pending = [m for m in self.items.values() if m.user_id is None]
        if query:
            found = [m for m in pending if query in (m.contact_name or "")]
        else:
            found = [
                m for m in pending if m.contact_name == name or (phone and m.contact_phone == phone)
            ]
        return found[:limit]

    async def list_page(
        self,
        *,
        query: str | None,
        is_active: bool | None,
        limit: int,
        offset: int,
        registered: bool | None = None,
    ) -> tuple[list[Mentor], int]:
        matched = [
            m
            for m in self.items.values()
            if (is_active is None or m.is_active == is_active)
            and (registered is None or m.is_registered == registered)
        ]
        return matched[offset : offset + limit], len(matched)


class InMemoryInstructorRepository:
    def __init__(self, *instructor_ids: uuid.UUID) -> None:
        self.ids = set(instructor_ids)

    async def exists(self, instructor_id: uuid.UUID) -> bool:
        return instructor_id in self.ids


class InMemoryContractFileRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, ContractFile] = {}

    async def add(self, file: ContractFile) -> None:
        self.items[file.id] = file

    async def save(self, file: ContractFile) -> None:
        self.items[file.id] = file

    async def get(self, file_id: uuid.UUID) -> ContractFile | None:
        return self.items.get(file_id)

    async def list_by_ids(self, file_ids: list[uuid.UUID]) -> list[ContractFile]:
        return [self.items[i] for i in file_ids if i in self.items]


class FakeFileStorage:
    """올린 객체를 메모리에 둔다. `upload`로 브라우저 업로드를 흉내 낸다."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []

    def upload(self, key: str, body: bytes, content_type: str = "application/pdf") -> None:
        self.objects[key] = (body, content_type)

    async def presign_post(
        self, key: str, *, content_type: str, max_bytes: int, now: datetime
    ) -> PresignedPost:
        return PresignedPost(
            url="https://s3.test/bucket",
            fields={"key": key, "Content-Type": content_type},
            expires_at=now + POST_TTL,
        )

    async def presign_get(self, key: str, *, download_name: str | None = None) -> str:
        return f"https://s3.test/bucket/{key}?download={download_name}"

    async def head(self, key: str) -> ObjectInfo | None:
        found = self.objects.get(key)
        return ObjectInfo(size=len(found[0]), content_type=found[1]) if found else None

    async def read_prefix(self, key: str, length: int) -> bytes | None:
        found = self.objects.get(key)
        return found[0][:length] if found else None

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)


class FakeEmployeeDirectory:
    def __init__(self, *employee_ids: uuid.UUID) -> None:
        self.ids = set(employee_ids)

    async def exists(self, employee_id: uuid.UUID) -> bool:
        return employee_id in self.ids

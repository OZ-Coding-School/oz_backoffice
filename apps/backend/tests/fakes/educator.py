"""educator 인메모리 리포지토리와 가짜 파일 저장소·직원 조회."""

import dataclasses
import uuid
from datetime import date, datetime, timedelta

from app.contexts.educator.domain.entities import ContractFile, EducatorContract
from app.contexts.educator.domain.enums import ContractStatus
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
            if not contract_filter.statuses or c.status in contract_filter.statuses
        ]
        return matched[offset : offset + limit], len(matched)

    async def list_active_ended_before(self, today: date) -> list[EducatorContract]:
        return [
            dataclasses.replace(c)
            for c in self.items.values()
            if c.status is ContractStatus.ACTIVE and c.end_date < today
        ]


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

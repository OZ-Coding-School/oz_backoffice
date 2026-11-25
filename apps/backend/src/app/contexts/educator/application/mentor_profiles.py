"""멘토 프로필 (decisions A22, A28).

- 멘토 본인(`/me/mentor-profile`)과 운영진 대리 수정(`/admin/mentors/{id}/profile`,
  contract.manage)이 같은 서비스를 쓴다. 모든 변경은 감사 로그를 남긴다.
- 사진: 브라우저가 최적화해 올리고 서버는 형식만 검사한다(PNG·JPEG·WebP, 2MB, 매직 바이트).
  확정하면 바로 프로필에 반영하고, 이전 사진 객체는 커밋 후 지운다(기록 보존 안 함).
- 사진 URL은 조회할 때마다 presigned GET으로 발급한다(비공개 버킷, C5).
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.ports import FileStorage
from app.contexts.educator.application.uploads import DirectUploads, UploadSpec, UploadTicket
from app.contexts.educator.domain.profiles import PROFILE_FIELDS, Mentor
from app.contexts.educator.domain.repositories import EducatorContractRepository, MentorRepository
from app.core.uow import UnitOfWork
from app.shared.errors import NotFoundError

PROFILE_IMAGE_MAX_BYTES = 2 * 1024 * 1024
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
IMAGE_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
TARGET = "mentor"


def is_image(head: bytes, content_type: str) -> bool:
    """앞부분이 Content-Type이 말하는 이미지 형식인지 (PNG·JPEG·WebP 시그니처)."""
    if content_type == "image/png":
        return head.startswith(_PNG)
    if content_type == "image/jpeg":
        return head.startswith(_JPEG)
    if content_type == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def image_upload_spec(mentor_id: uuid.UUID) -> UploadSpec:
    # 용도에 멘토 ID를 넣어 다른 멘토의 사진으로 확정할 수 없게 한다
    return UploadSpec(
        purpose=f"mentor_image:{mentor_id}",
        key_prefix="profiles/",
        extensions=IMAGE_EXTENSIONS,
        max_bytes=PROFILE_IMAGE_MAX_BYTES,
        magic_length=12,
        is_valid_format=is_image,
        invalid_code="invalid_profile_image",
        invalid_message="PNG·JPEG·WebP 이미지가 아니거나 2MB를 넘었습니다.",
    )


@dataclass(frozen=True, slots=True)
class MentorSummary:
    mentor: Mentor
    contract_count: int


def _snapshot(mentor: Mentor) -> dict[str, Any]:
    values: dict[str, Any] = {name: getattr(mentor, name) for name in sorted(PROFILE_FIELDS)}
    values["profile_image_key"] = mentor.profile_image_key
    return {k: v.value if isinstance(v, Enum) else v for k, v in values.items()}


class MentorProfileService:
    def __init__(
        self,
        *,
        mentors: MentorRepository,
        contracts: EducatorContractRepository,
        uploads: DirectUploads,
        storage: FileStorage,
        audit: AuditRecorder,
        uow: UnitOfWork,
    ) -> None:
        self._mentors = mentors
        self._contracts = contracts
        self._uploads = uploads
        self._storage = storage
        self._audit = audit
        self._uow = uow

    # ------------------------------------------------------------------ 조회
    async def get(self, mentor_id: uuid.UUID) -> Mentor:
        mentor = await self._mentors.get(mentor_id)
        if mentor is None:
            raise NotFoundError("멘토를 찾을 수 없습니다.", code="mentor_not_found")
        return mentor

    async def get_by_user(self, user_id: uuid.UUID) -> Mentor:
        mentor = await self._mentors.get_by_user(user_id)
        if mentor is None:
            raise NotFoundError("멘토 프로필이 없습니다.", code="mentor_profile_not_found")
        return mentor

    async def image_url(self, mentor: Mentor) -> str | None:
        if mentor.profile_image_key is None:
            return None
        return await self._storage.presign_get(mentor.profile_image_key)

    async def list_mentors(
        self, *, query: str | None, is_active: bool | None, limit: int, offset: int
    ) -> tuple[list[MentorSummary], int]:
        mentors, total = await self._mentors.list_page(
            query=query, is_active=is_active, limit=limit, offset=offset
        )
        counts = await self._contracts.count_by_mentors([m.id for m in mentors])
        return [MentorSummary(m, counts.get(m.id, 0)) for m in mentors], total

    async def summary(self, mentor_id: uuid.UUID) -> MentorSummary:
        """멘토 하나의 목록 항목 (A102). 없으면 404 mentor_not_found"""
        mentor = await self.get(mentor_id)
        counts = await self._contracts.count_by_mentors([mentor.id])
        return MentorSummary(mentor, counts.get(mentor.id, 0))

    # ------------------------------------------------------------------ 변경
    async def update(
        self, mentor_id: uuid.UUID, changes: dict[str, Any], *, actor_id: uuid.UUID
    ) -> Mentor:
        async with self._uow:
            current = await self.get(mentor_id)
            updated = current.with_profile(changes)
            await self._mentors.save(updated)
            await self._record(actor_id, "profile_update", updated, before=current)
        return updated

    async def request_image_upload(
        self, mentor_id: uuid.UUID, content_type: str, *, actor_id: uuid.UUID
    ) -> UploadTicket:
        await self.get(mentor_id)
        return await self._uploads.issue(
            image_upload_spec(mentor_id), actor_id=actor_id, content_type=content_type
        )

    async def confirm_image(
        self, mentor_id: uuid.UUID, upload_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> Mentor:
        received = await self._uploads.receive(
            image_upload_spec(mentor_id), upload_id, actor_id=actor_id
        )
        return await self._replace_image(
            mentor_id, received.upload.storage_key, actor_id=actor_id, action="image_update"
        )

    async def delete_image(self, mentor_id: uuid.UUID, *, actor_id: uuid.UUID) -> Mentor:
        return await self._replace_image(mentor_id, None, actor_id=actor_id, action="image_delete")

    # ------------------------------------------------------------------ 내부
    async def _replace_image(
        self, mentor_id: uuid.UUID, key: str | None, *, actor_id: uuid.UUID, action: str
    ) -> Mentor:
        async with self._uow:
            mentor = await self.get(mentor_id)
            before = _snapshot(mentor)
            previous = mentor.replace_image(key)
            await self._mentors.save(mentor)
            await self._audit.record(
                actor_user_id=actor_id,
                action=f"educator.mentor.{action}",
                target_type=TARGET,
                target_id=mentor.id,
                before=before,
                after=_snapshot(mentor),
            )
            if previous is not None:
                self._uow.on_commit(lambda: self._storage.delete(previous))
        return mentor

    async def _record(
        self, actor_id: uuid.UUID, action: str, mentor: Mentor, *, before: Mentor
    ) -> None:
        await self._audit.record(
            actor_user_id=actor_id,
            action=f"educator.mentor.{action}",
            target_type=TARGET,
            target_id=mentor.id,
            before=_snapshot(before),
            after=_snapshot(mentor),
        )

from datetime import UTC, datetime

import pytest
from fakeredis import FakeAsyncRedis

from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_profiles import (
    PROFILE_IMAGE_MAX_BYTES,
    MentorProfileService,
)
from app.contexts.educator.application.uploads import DirectUploads
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.educator.infrastructure.pending_uploads import RedisPendingUploadStore
from app.core.clock import FixedClock
from app.shared.errors import BusinessRuleViolation, NotFoundError
from app.shared.ids import new_id
from tests.fakes.audit import InMemoryAuditLogRepository
from tests.fakes.educator import (
    FakeFileStorage,
    InMemoryContractRepository,
    InMemoryMentorRepository,
)
from tests.fakes.uow import FakeUnitOfWork

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


class Harness:
    def __init__(self, redis: FakeAsyncRedis) -> None:
        clock = FixedClock(NOW)
        self.storage = FakeFileStorage()
        self.mentor = Mentor(user_id=new_id())
        self.mentors = InMemoryMentorRepository(self.mentor)
        self.audit_logs = InMemoryAuditLogRepository()
        self.uploads = DirectUploads(
            storage=self.storage, pending=RedisPendingUploadStore(redis), clock=clock
        )
        self.service = MentorProfileService(
            mentors=self.mentors,
            contracts=InMemoryContractRepository(),
            uploads=self.uploads,
            storage=self.storage,
            audit=AuditRecorder(self.audit_logs, clock),
            uow=FakeUnitOfWork(),
        )

    async def upload_image(self, body: bytes = PNG, content_type: str = "image/png") -> Mentor:
        ticket = await self.service.request_image_upload(
            self.mentor.id, content_type, actor_id=self.mentor.user_id
        )
        self.storage.upload(ticket.fields["key"], body, content_type)
        return await self.service.confirm_image(
            self.mentor.id, ticket.upload_id, actor_id=self.mentor.user_id
        )


@pytest.fixture
def h(fake_redis: FakeAsyncRedis) -> Harness:
    return Harness(fake_redis)


async def test_update_profile_records_audit(h: Harness) -> None:
    updated = await h.service.update(
        h.mentor.id, {"headline": "백엔드 10년차", "nickname": "오즈"}, actor_id=new_id()
    )
    assert (updated.headline, updated.nickname) == ("백엔드 10년차", "오즈")
    log = h.audit_logs.logs[-1]
    assert log.action == "educator.mentor.profile_update"
    assert log.before is not None
    assert log.after is not None
    assert (log.before["headline"], log.after["headline"]) == (None, "백엔드 10년차")


async def test_image_upload_replaces_and_deletes_previous(h: Harness) -> None:
    first = await h.upload_image()
    first_key = first.profile_image_key
    assert first_key is not None
    assert first_key.startswith("profiles/")
    assert first_key.endswith(".png")
    assert await h.service.image_url(first) == f"https://s3.test/bucket/{first_key}?download=None"

    second = await h.upload_image(b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")
    assert second.profile_image_key is not None
    assert second.profile_image_key.endswith(".jpg")
    assert h.storage.deleted == [first_key]  # 이전 사진은 커밋 후 지운다

    cleared = await h.service.delete_image(h.mentor.id, actor_id=h.mentor.user_id)
    assert cleared.profile_image_key is None
    assert h.storage.deleted == [first_key, second.profile_image_key]
    assert [log.action for log in h.audit_logs.logs] == [
        "educator.mentor.image_update",
        "educator.mentor.image_update",
        "educator.mentor.image_delete",
    ]


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"%PDF-1.7" + b"0" * 50, "image/png"),  # 이미지가 아님
        (b"\x89PNG\r\n\x1a\n" + b"0" * PROFILE_IMAGE_MAX_BYTES, "image/png"),  # 2MB 초과
    ],
)
async def test_invalid_image_is_rejected_and_deleted(
    h: Harness, body: bytes, content_type: str
) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        await h.upload_image(body, content_type)
    assert exc.value.code == "invalid_profile_image"
    assert len(h.storage.deleted) == 1
    assert (await h.service.get(h.mentor.id)).profile_image_key is None


async def test_upload_rules(h: Harness) -> None:
    with pytest.raises(BusinessRuleViolation) as unsupported:
        await h.service.request_image_upload(h.mentor.id, "image/gif", actor_id=h.mentor.user_id)
    assert unsupported.value.code == "unsupported_file_type"
    with pytest.raises(NotFoundError) as missing:
        await h.service.request_image_upload(new_id(), "image/png", actor_id=h.mentor.user_id)
    assert missing.value.code == "mentor_not_found"

    # 다른 멘토의 사진 업로드 ID로는 확정할 수 없다 (용도에 멘토 ID 포함)
    other = Mentor(user_id=new_id())
    await h.mentors.save(other)
    ticket = await h.service.request_image_upload(other.id, "image/png", actor_id=h.mentor.user_id)
    h.storage.upload(ticket.fields["key"], PNG, "image/png")
    with pytest.raises(NotFoundError):
        await h.service.confirm_image(h.mentor.id, ticket.upload_id, actor_id=h.mentor.user_id)


async def test_get_by_user(h: Harness) -> None:
    assert (await h.service.get_by_user(h.mentor.user_id)).id == h.mentor.id
    with pytest.raises(NotFoundError) as exc:
        await h.service.get_by_user(new_id())
    assert exc.value.code == "mentor_profile_not_found"

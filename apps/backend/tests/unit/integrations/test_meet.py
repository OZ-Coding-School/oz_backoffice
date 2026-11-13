"""Google Meet 어댑터 (공식 클라이언트를 가짜로 바꿔 끼움, A46·A48)."""

from typing import Any

import pytest
from google.api_core import exceptions as google_exceptions
from google.apps.meet_v2 import types as meet

from app.core.config import Settings
from app.core.meet import build_meet_client
from app.integrations.google.meet import GoogleMeetClient, MeetUnavailableError

pytestmark = pytest.mark.unit


def _error(kind: type[Exception], message: str) -> Exception:
    return kind(message)  # api_core 예외 생성자는 타입이 없다


class FakeSpacesApi:
    def __init__(self) -> None:
        self.requests: list[tuple[str, Any]] = []
        self.errors: dict[str, Exception] = {}

    async def _call(self, name: str, request: Any) -> Any:
        self.requests.append((name, request))
        if name in self.errors:
            raise self.errors[name]
        return meet.Space(name="spaces/abc", meeting_uri="https://meet.google.com/abc-defg-hij")

    async def create_space(self, *, request: Any) -> Any:
        return await self._call("create", request)

    async def update_space(self, *, request: Any) -> Any:
        return await self._call("update", request)

    async def end_active_conference(self, *, request: Any) -> Any:
        return await self._call("end", request)

    async def create_member(self, *, request: Any) -> Any:
        return await self._call("member", request)


async def test_create_space_config() -> None:
    api = FakeSpacesApi()
    space = await GoogleMeetClient(api).create_space()
    assert (space.name, space.meeting_uri) == ("spaces/abc", "https://meet.google.com/abc-defg-hij")
    config = api.requests[0][1].space.config
    on = meet.SpaceConfig.ArtifactConfig.AutoGenerationType.ON
    assert config.access_type == meet.SpaceConfig.AccessType.OPEN
    assert config.moderation == meet.SpaceConfig.Moderation.ON  # 공동 주최자 역할이 적용되게
    free = meet.SpaceConfig.ModerationRestrictions.RestrictionType.NO_RESTRICTION
    assert config.moderation_restrictions.chat_restriction == free
    assert config.moderation_restrictions.present_restriction == free
    assert config.artifact_config.recording_config.auto_recording_generation == on
    assert config.artifact_config.transcription_config.auto_transcription_generation == on
    assert config.artifact_config.smart_notes_config.auto_smart_notes_generation == on

    api.errors["create"] = _error(google_exceptions.PermissionDenied, "위임 없음")
    with pytest.raises(MeetUnavailableError):
        await GoogleMeetClient(api).create_space()


async def test_restrict_space() -> None:
    api = FakeSpacesApi()
    client = GoogleMeetClient(api)
    api.errors["end"] = _error(google_exceptions.FailedPrecondition, "회의 없음")
    await client.restrict_space("spaces/abc")  # 진행 중인 회의가 없으면 무시
    update = api.requests[0][1]
    assert (update.space.name, list(update.update_mask.paths)) == (
        "spaces/abc",
        ["config.access_type"],
    )
    assert update.space.config.access_type == meet.SpaceConfig.AccessType.RESTRICTED

    api.errors = {"update": _error(google_exceptions.NotFound, "없음")}
    await client.restrict_space("spaces/gone")  # 없는 공간은 무시
    api.errors = {"update": _error(google_exceptions.ServiceUnavailable, "장애")}
    with pytest.raises(MeetUnavailableError):
        await client.restrict_space("spaces/abc")


def test_build_meet_client(settings: Settings) -> None:
    assert build_meet_client(settings) is None  # 기본 disabled
    missing = settings.model_copy(update={"meet_driver": "google"})
    assert build_meet_client(missing) is None  # 키·주최 계정 없음


async def test_add_cohost() -> None:
    api = FakeSpacesApi()
    client = GoogleMeetClient(api)
    await client.add_cohost("spaces/abc", "mentor@example.com")
    request = api.requests[-1][1]
    assert (request.parent, request.member.email, request.member.role) == (
        "spaces/abc",
        "mentor@example.com",
        meet.Member.Role.COHOST,
    )
    api.errors["member"] = _error(google_exceptions.AlreadyExists, "이미 있음")
    await client.add_cohost("spaces/abc", "mentor@example.com")  # 이미 등록돼 있으면 무시
    api.errors["member"] = _error(google_exceptions.PermissionDenied, "권한")
    with pytest.raises(MeetUnavailableError):
        await client.add_cohost("spaces/abc", "mentor@example.com")

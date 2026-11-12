"""Google Meet REST API 어댑터 (decisions A8·A46·A47·A48).

서비스 계정이 도메인 전체 위임으로 주최 계정(`GMAIL_SENDER`)을 대신해 공간을 만든다.
- 생성: 링크가 있으면 바로 입장(OPEN), 녹화·전사·스마트 메모 자동 생성(라이선스가 지원하는 것만).
- 막기: 취소된 세션의 공간을 입장 제한(RESTRICTED)으로 바꾸고 진행 중인 회의를 끝낸다.
공식 라이브러리(`google-apps-meet`)의 비동기 클라이언트를 쓴다.
실패는 `MeetUnavailableError`(503)로 바꾼다.
"""

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from google.api_core import exceptions as google_exceptions
from google.apps.meet_v2 import SpacesServiceAsyncClient
from google.apps.meet_v2 import types as meet
from google.oauth2 import service_account

from app.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

MEET_SPACE_SCOPE = "https://www.googleapis.com/auth/meetings.space.created"


class MeetUnavailableError(ServiceUnavailableError):
    def __init__(self, message: str = "Google Meet 공간을 처리하지 못했습니다.") -> None:
        super().__init__(message, code="meet_unavailable")


@dataclass(frozen=True, slots=True)
class MeetSpace:
    name: str  # spaces/xxx
    meeting_uri: str


class SpacesApi(Protocol):
    """`SpacesServiceAsyncClient`에서 쓰는 부분 (테스트에서 바꿔 끼운다)."""

    async def create_space(self, *, request: Any) -> Any: ...
    async def update_space(self, *, request: Any) -> Any: ...
    async def end_active_conference(self, *, request: Any) -> Any: ...


def _new_space_config() -> meet.SpaceConfig:
    auto = meet.SpaceConfig.ArtifactConfig
    on = meet.SpaceConfig.ArtifactConfig.AutoGenerationType.ON
    return meet.SpaceConfig(
        access_type=meet.SpaceConfig.AccessType.OPEN,
        entry_point_access=meet.SpaceConfig.EntryPointAccess.ALL,
        artifact_config=auto(
            recording_config=auto.RecordingConfig(auto_recording_generation=on),
            transcription_config=auto.TranscriptionConfig(auto_transcription_generation=on),
            smart_notes_config=auto.SmartNotesConfig(auto_smart_notes_generation=on),
        ),
    )


def build_spaces_api(service_account_info: dict[str, Any], organizer: str) -> SpacesApi:
    credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]  # google-auth 타입 없음
        service_account_info, scopes=[MEET_SPACE_SCOPE], subject=organizer
    )
    return SpacesServiceAsyncClient(credentials=credentials)


class GoogleMeetClient:
    def __init__(self, api: SpacesApi) -> None:
        self._api = api

    async def create_space(self) -> MeetSpace:
        request = meet.CreateSpaceRequest(space=meet.Space(config=_new_space_config()))
        try:
            space = await self._api.create_space(request=request)
        except google_exceptions.GoogleAPICallError as exc:
            logger.warning("Meet 공간 생성 실패: %s", type(exc).__name__)
            raise MeetUnavailableError() from exc
        return MeetSpace(name=space.name, meeting_uri=space.meeting_uri)

    async def restrict_space(self, space_name: str) -> None:
        """입장 제한으로 바꾸고 진행 중인 회의가 있으면 끝낸다 (없으면 무시)."""
        request = meet.UpdateSpaceRequest(
            space=meet.Space(
                name=space_name,
                config=meet.SpaceConfig(access_type=meet.SpaceConfig.AccessType.RESTRICTED),
            ),
            update_mask={"paths": ["config.access_type"]},
        )
        try:
            await self._api.update_space(request=request)
        except google_exceptions.NotFound:
            return  # 이미 없는 공간
        except google_exceptions.GoogleAPICallError as exc:
            logger.warning("Meet 공간 막기 실패(%s): %s", space_name, type(exc).__name__)
            raise MeetUnavailableError() from exc
        try:
            await self._api.end_active_conference(
                request=meet.EndActiveConferenceRequest(name=space_name)
            )
        except (google_exceptions.NotFound, google_exceptions.FailedPrecondition):
            return  # 진행 중인 회의 없음
        except google_exceptions.GoogleAPICallError as exc:
            logger.warning("Meet 회의 종료 실패(%s): %s", space_name, type(exc).__name__)
            raise MeetUnavailableError() from exc

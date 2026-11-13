"""Google Drive 어댑터: 녹화 폴더 정리와 파일 중계 (decisions M19·A53·A54).

- 폴더: 공유 드라이브 `멘토링 녹화`(설정 `MEET_RECORDINGS_FOLDER_ID`) 아래에
  `과정명/N기/멘토 실명/YYYY-MM` 폴더를 찾거나 만든다. 서비스 계정 자신의 권한(공유 드라이브 멤버).
- 이동: 개인 Drive의 파일을 공유 드라이브로 옮기는 것은 소유자만 할 수 있어 위임(drive)으로
  주최 계정을 대신해 옮긴다.
- 정보·중계: 서비스 계정 자신의 권한으로 이름·형식·크기를 읽고, 영상은 Range를 그대로 넘겨 스트리밍,
  Google 문서(전사·요약)는 PDF로 내보내 스트리밍한다. 파일 전체를 메모리에 올리지 않는다.
동기 클라이언트(google-api-python-client) 호출은 스레드에서 한다.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from google.auth.transport.requests import Request as AuthRequest
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.shared.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME = "application/vnd.google-apps.folder"
PDF_MIME = "application/pdf"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
PASSED_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges")


class DriveUnavailableError(ServiceUnavailableError):
    def __init__(self, message: str = "Google Drive 파일을 처리하지 못했습니다.") -> None:
        super().__init__(message, code="drive_unavailable")


@dataclass(frozen=True, slots=True)
class DriveFile:
    name: str
    mime_type: str
    size: int | None


@dataclass(slots=True)
class DriveStream:
    """중계할 응답. `chunks`를 끝까지 읽거나 `close()`해야 연결이 닫힌다."""

    status_code: int
    headers: dict[str, str]
    chunks: AsyncIterator[bytes]
    close: Callable[[], Any] = field(default=lambda: None)


class Credentials(Protocol):
    token: str | None

    def refresh(self, request: Any) -> None: ...


def _quote(name: str) -> str:
    return name.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveArchive:
    def __init__(
        self,
        *,
        files: Any,  # 서비스 계정 자신의 drive v3 `files()` 리소스
        owner_files: Any,  # 위임(주최 계정) drive v3 `files()` 리소스
        credentials: Credentials,  # 중계용(서비스 계정 자신)
        root_folder_id: str,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._files = files
        self._owner_files = owner_files
        self._credentials = credentials
        self._root = root_folder_id
        self._http = http

    # ------------------------------------------------------------------ 폴더·이동
    async def ensure_folder(self, path: list[str]) -> str:
        """루트 아래 path를 차례로 찾거나 만든다. 마지막 폴더 ID."""
        parent = self._root
        for name in path:
            parent = await self._child_folder(parent, name)
        return parent

    async def _child_folder(self, parent: str, name: str) -> str:
        query = (
            f"'{parent}' in parents and name = '{_quote(name)}' "
            f"and mimeType = '{FOLDER_MIME}' and trashed = false"
        )
        found = await self._call(
            lambda: self._files.list(
                q=query,
                fields="files(id)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=1,
            ).execute()
        )
        if found.get("files"):
            return str(found["files"][0]["id"])
        created = await self._call(
            lambda: self._files.create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]},
                fields="id",
                supportsAllDrives=True,
            ).execute()
        )
        return str(created["id"])

    async def move(self, file_id: str, folder_id: str) -> None:
        """주최 계정(소유자)으로 옮긴다. 이미 그 폴더에 있으면 그대로."""
        current = await self._call(
            lambda: self._owner_files.get(
                fileId=file_id, fields="parents", supportsAllDrives=True
            ).execute()
        )
        parents = list(current.get("parents") or [])
        if parents == [folder_id]:
            return
        await self._call(
            lambda: self._owner_files.update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=",".join(p for p in parents if p != folder_id),
                supportsAllDrives=True,
                fields="id",
            ).execute()
        )

    async def describe(self, file_id: str) -> DriveFile:
        meta = await self._call(
            lambda: self._files.get(
                fileId=file_id, fields="name,mimeType,size", supportsAllDrives=True
            ).execute()
        )
        size = meta.get("size")
        return DriveFile(
            name=str(meta["name"]),
            mime_type=str(meta["mimeType"]),
            size=int(size) if size else None,
        )

    @staticmethod
    async def _call(action: Callable[[], Any]) -> Any:
        try:
            return await asyncio.to_thread(action)
        except HttpError as exc:
            logger.warning("Drive 호출 실패: %s", exc.resp.status)
            raise DriveUnavailableError() from exc

    # ------------------------------------------------------------------ 중계
    async def stream(
        self, file_id: str, *, export_pdf: bool, range_header: str | None
    ) -> DriveStream:
        await asyncio.to_thread(self._credentials.refresh, AuthRequest())
        # 받은 바이트를 그대로 넘기므로 압축하지 않은 응답을 받는다(압축되면 PDF·영상 구간이 깨진다)
        headers = {
            "Authorization": f"Bearer {self._credentials.token}",
            "Accept-Encoding": "identity",
        }
        if export_pdf:
            url = f"{FILES_URL}/{file_id}/export"
            params = {"mimeType": PDF_MIME}
        else:
            url = f"{FILES_URL}/{file_id}"
            params = {"alt": "media", "supportsAllDrives": "true"}
            if range_header:
                headers["Range"] = range_header
        http = self._http or httpx.AsyncClient(timeout=httpx.Timeout(30, read=None))
        request = http.build_request("GET", url, params=params, headers=headers)
        response = await http.send(request, stream=True)
        if response.status_code not in (200, 206):
            await response.aclose()
            if self._http is None:
                await http.aclose()
            if response.status_code == 416:
                raise DriveUnavailableError("요청한 범위를 줄 수 없습니다.")
            logger.warning("Drive 중계 실패(%s): %s", file_id, response.status_code)
            raise DriveUnavailableError()

        async def close() -> None:
            await response.aclose()
            if self._http is None:
                await http.aclose()

        async def chunks() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_raw():
                    yield chunk
            finally:
                await close()

        passed = {k: v for k, v in response.headers.items() if k.lower() in PASSED_HEADERS}
        if export_pdf:
            passed["content-type"] = PDF_MIME
        return DriveStream(response.status_code, passed, chunks(), close)


def build_drive_archive(
    service_account_info: dict[str, Any], organizer: str, root_folder_id: str
) -> GoogleDriveArchive:
    own = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]  # google-auth 타입 없음
        service_account_info, scopes=[DRIVE_SCOPE]
    )
    owner = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
        service_account_info, scopes=[DRIVE_SCOPE], subject=organizer
    )
    return GoogleDriveArchive(
        files=build("drive", "v3", credentials=own, cache_discovery=False).files(),
        owner_files=build("drive", "v3", credentials=owner, cache_discovery=False).files(),
        credentials=own,
        root_folder_id=root_folder_id,
    )

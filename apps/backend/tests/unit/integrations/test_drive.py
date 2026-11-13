"""Google Drive 어댑터: 폴더 찾기·만들기, 소유자 이동, 정보, 중계 (가짜 리소스 + respx, A54)."""

from typing import Any

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.meet import build_drive_archive_client
from app.integrations.google.drive import (
    FILES_URL,
    FOLDER_MIME,
    DriveUnavailableError,
    GoogleDriveArchive,
)

pytestmark = pytest.mark.unit


class Call:
    def __init__(self, result: Any) -> None:
        self.result = result

    def execute(self) -> Any:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeFiles:
    """drive v3 files() 리소스 흉내: 폴더 트리와 파일 부모를 기억한다."""

    def __init__(self) -> None:
        self.folders: dict[tuple[str, str], str] = {}  # (부모, 이름) → ID
        self.parents: dict[str, list[str]] = {"rec1": ["meet-folder"]}
        self.calls: list[str] = []

    def list(self, *, q: str, **_: Any) -> Call:
        self.calls.append("list")
        parent = q.split("'")[1]
        name = q.split("name = '")[1].split("' and")[0].replace("\\\\'", "'")
        found = self.folders.get((parent, name))
        return Call({"files": [{"id": found}] if found else []})

    def create(self, *, body: dict[str, Any], **_: Any) -> Call:
        self.calls.append("create")
        assert body["mimeType"] == FOLDER_MIME
        new_id = f"f{len(self.folders) + 1}"
        self.folders[(body["parents"][0], body["name"])] = new_id
        return Call({"id": new_id})

    def get(self, *, fileId: str, fields: str, **_: Any) -> Call:
        if fields == "parents":
            return Call({"parents": self.parents[fileId]})
        return Call({"name": "녹화.mp4", "mimeType": "video/mp4", "size": "2048"})

    def update(self, *, fileId: str, addParents: str, removeParents: str, **_: Any) -> Call:
        self.calls.append(f"move:{removeParents}->{addParents}")
        self.parents[fileId] = [addParents]
        return Call({"id": fileId})


class FakeCredentials:
    token: str | None = "token"

    def refresh(self, request: Any) -> None:
        return None


def _archive(files: FakeFiles, http: httpx.AsyncClient | None = None) -> GoogleDriveArchive:
    return GoogleDriveArchive(
        files=files,
        owner_files=files,
        credentials=FakeCredentials(),
        root_folder_id="root",
        http=http,
    )


async def test_folders_move_and_describe() -> None:
    files = FakeFiles()
    archive = _archive(files)
    path = ["BX 디자이너", "4기", "김멘토", "2026-11"]
    folder = await archive.ensure_folder(path)
    assert folder == "f4"
    assert files.calls.count("create") == 4
    assert await archive.ensure_folder(path) == "f4"  # 이미 있으면 찾기만
    assert files.calls.count("create") == 4
    assert await archive.ensure_folder(["O'Reilly"]) == "f5"  # 따옴표 이스케이프

    await archive.move("rec1", folder)
    assert files.parents["rec1"] == [folder]
    await archive.move("rec1", folder)  # 이미 그 폴더
    assert [c for c in files.calls if c.startswith("move")] == ["move:meet-folder->f4"]
    described = await archive.describe("rec1")
    assert (described.name, described.mime_type, described.size) == ("녹화.mp4", "video/mp4", 2048)


async def test_drive_errors_become_unavailable() -> None:
    from googleapiclient.errors import HttpError
    from httplib2 import Response

    class Failing(FakeFiles):
        def get(self, *, fileId: str, fields: str, **_: Any) -> Call:
            return Call(HttpError(Response({"status": "403"}), b"{}"))

    with pytest.raises(DriveUnavailableError):
        await _archive(Failing()).describe("x")


@respx.mock
async def test_stream_video_range_and_pdf_export() -> None:
    respx.get(f"{FILES_URL}/v1").mock(
        return_value=httpx.Response(
            206,
            content=b"abc",
            headers={"Content-Range": "bytes 0-2/10", "Content-Type": "video/mp4", "X-Other": "1"},
        )
    )
    respx.get(f"{FILES_URL}/d1/export").mock(
        return_value=httpx.Response(200, content=b"%PDF", headers={"Content-Type": "x"})
    )
    respx.get(f"{FILES_URL}/gone").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as http:
        archive = _archive(FakeFiles(), http)
        video = await archive.stream("v1", export_pdf=False, range_header="bytes=0-2")
        assert video.status_code == 206
        assert video.headers["content-range"] == "bytes 0-2/10"
        assert "x-other" not in video.headers
        assert b"".join([c async for c in video.chunks]) == b"abc"
        sent = respx.calls[0].request
        assert (sent.headers["range"], sent.headers["authorization"]) == (
            "bytes=0-2",
            "Bearer token",
        )
        assert sent.url.params["alt"] == "media"

        pdf = await archive.stream("d1", export_pdf=True, range_header="bytes=0-2")
        assert (pdf.status_code, pdf.headers["content-type"]) == (200, "application/pdf")
        assert "range" not in respx.calls[1].request.headers  # 내보내기는 Range 없이
        assert respx.calls[1].request.url.params["mimeType"] == "application/pdf"
        await pdf.close()

        with pytest.raises(DriveUnavailableError):
            await archive.stream("gone", export_pdf=False, range_header=None)


def test_drive_client_needs_settings(settings: Settings) -> None:
    assert build_drive_archive_client(settings) is None
    on = settings.model_copy(update={"meet_driver": "google"})
    assert build_drive_archive_client(on) is None  # 폴더 ID 없음
    with_folder = on.model_copy(update={"meet_recordings_folder_id": "root"})
    assert build_drive_archive_client(with_folder) is None  # 키 없음

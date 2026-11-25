"""녹화·전사·요약 수집·정리·열람 서비스 (인메모리 + 가짜 Meet·Drive, A53·A54)."""

import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.contexts.academy.domain.entities import Student
from app.contexts.academy.domain.enums import StudentStatus
from app.contexts.educator.application.mentor_queries import MentorQueries
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.application.artifact_service import ArtifactService
from app.contexts.mentoring.application.session_service import MentoringSessionQueries
from app.contexts.mentoring.domain.enums import MentoringArtifactStatus, MentoringArtifactType
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession
from app.core.clock import FixedClock
from app.integrations.google.drive import DriveFile, DriveStream, DriveUnavailableError
from app.integrations.google.meet import MeetUnavailableError
from app.integrations.google.meet_events import MeetFile, MeetTranscriptLine
from app.shared.errors import NotFoundError
from app.shared.ids import new_id
from tests.factories.identity import make_user
from tests.fakes.educator import InMemoryMentorRepository
from tests.fakes.mentoring import (
    InMemoryArtifactRepository,
    InMemoryRequestRepository,
    InMemorySessionRepository,
    InMemoryTeamRepository,
    InMemoryTranscriptEntryRepository,
)

pytestmark = pytest.mark.unit

START = datetime(2026, 11, 19, 15, 30, tzinfo=UTC)  # 11-20 00:30 KST → 2026-11 폴더


@dataclass
class Label:
    bootcamp_name: str
    cohort_number: int


class Cohorts:
    def __init__(self, cohort_id: uuid.UUID) -> None:
        self.cohort_id = cohort_id

    async def cohort_labels(self, cohort_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Any]:
        return {self.cohort_id: Label("BX 디자이너", 4)}


class Students:
    def __init__(self, *students: Student) -> None:
        self.items = {s.id: s for s in students}

    async def get_many(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]:
        return {i: self.items[i] for i in ids if i in self.items}

    async def of_user(self, user_id: uuid.UUID) -> list[Student]:
        return [s for s in self.items.values() if s.user_id == user_id]


class Users:
    def __init__(self, *users: User) -> None:
        self.items = {u.id: u for u in users}

    async def get_many(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
        return {i: self.items[i] for i in ids if i in self.items}


class FakeSource:
    def __init__(self) -> None:
        self.files: list[MeetFile] = []
        self.lines: dict[str, list[MeetTranscriptLine]] = {}
        self.line_calls: list[str] = []
        self.lines_fail = False

    async def transcript_lines(self, transcript_name: str) -> list[MeetTranscriptLine]:
        self.line_calls.append(transcript_name)
        if self.lines_fail:
            raise MeetUnavailableError()
        return self.lines.get(transcript_name, [])

    async def session_files(self, space_name: str) -> list[MeetFile]:
        return list(self.files)


class FakeArchive:
    def __init__(self) -> None:
        self.folders: list[list[str]] = []
        self.moved: list[tuple[str, str]] = []
        self.fail = False
        self.streamed: list[tuple[str, bool, str | None]] = []

    async def ensure_folder(self, path: list[str]) -> str:
        if self.fail:
            raise DriveUnavailableError()
        self.folders.append(path)
        return "folder-1"

    async def move(self, file_id: str, folder_id: str) -> None:
        self.moved.append((file_id, folder_id))

    async def describe(self, file_id: str) -> DriveFile:
        return DriveFile(name=f"{file_id}.bin", mime_type="video/mp4", size=10)

    async def stream(
        self, file_id: str, *, export_pdf: bool, range_header: str | None
    ) -> DriveStream:
        self.streamed.append((file_id, export_pdf, range_header))

        async def chunks() -> AsyncIterator[bytes]:
            yield b"x"

        return DriveStream(200, {}, chunks())

    async def export_markdown(self, file_id: str) -> str:
        return f"## {file_id}"


class Harness:
    def __init__(self) -> None:
        self.cohort_id = new_id()
        self.student = Student(
            cohort_id=self.cohort_id,
            name="가수강",
            hrd_net_status=StudentStatus.TRAINING,
            enrolled_at=date(2026, 11, 1),
            user_id=new_id(),
        )
        mentor_user = make_user(name="김멘토")
        self.mentor = Mentor(
            user_id=mentor_user.id,
            nickname="멘토K",
            display_name_preference=DisplayNamePreference.NICKNAME,
        )
        self.requests = InMemoryRequestRepository()
        self.sessions = InMemorySessionRepository(self.requests)
        self.artifacts = InMemoryArtifactRepository()
        self.entries = InMemoryTranscriptEntryRepository()
        self.source = FakeSource()
        self.archive = FakeArchive()
        self.clock = FixedClock(START + timedelta(hours=2))
        students = Students(self.student)
        mentors = MentorQueries(InMemoryMentorRepository(self.mentor))
        self.service = ArtifactService(
            sessions=self.sessions,
            requests=self.requests,
            artifacts=self.artifacts,
            access=MentoringSessionQueries(
                sessions=self.sessions,
                requests=self.requests,
                teams=InMemoryTeamRepository(),
                students=students,
                mentors=mentors,
            ),
            source=self.source,
            archive=self.archive,
            students=students,
            cohorts=Cohorts(self.cohort_id),
            mentors=mentors,
            users=Users(mentor_user),
            clock=self.clock,
            entries=self.entries,
            teams=InMemoryTeamRepository(),
        )

    async def session(self, hours: int = 0) -> MentoringSession:
        start = START + timedelta(hours=hours)
        request = MentoringRequest(
            requester_id=self.student.id,
            mentor_id=self.mentor.id,
            topic="주제",
            detail="내용",
            desired_times=[start],
            duration=60,
        )
        await self.requests.add(request)
        session = MentoringSession(
            mentor_id=self.mentor.id,
            request_id=request.id,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            title="제목",
            topic="주제",
        )
        session.attach_space("spaces/a", "https://meet.google.com/a")
        await self.sessions.add(session)
        return session


@pytest.fixture
def h() -> Harness:
    return Harness()


async def test_collect_archives_into_folder(h: Harness) -> None:
    session = await h.session()
    h.source.files = [
        MeetFile("VIDEO", "v1"),
        MeetFile("TRANSCRIPT", "t1"),
        MeetFile("SUMMARY", "n1"),
    ]
    assert await h.service.collect(session.id) == 3
    assert await h.service.collect(session.id) == 0  # 중복 수집 없음
    assert h.archive.folders[0] == ["BX 디자이너", "4기", "김멘토", "2026-11"]  # KST 시작일(실명)
    assert sorted(f for f, _ in h.archive.moved) == ["n1", "t1", "v1"]
    stored = list(h.artifacts.items.values())
    assert {a.status for a in stored} == {MentoringArtifactStatus.COMPLETED}
    assert {a.artifact_type for a in stored} == set(MentoringArtifactType)


async def test_failures_retry_then_fail_after_7_days(h: Harness) -> None:
    session = await h.session()
    h.source.files = [MeetFile("VIDEO", "v1")]
    h.archive.fail = True
    assert await h.service.collect(session.id) == 1
    (artifact,) = h.artifacts.items.values()
    assert artifact.status is MentoringArtifactStatus.PENDING  # 다음 주기에 다시
    h.archive.fail = False
    assert await h.service.sync() == (0, 1)
    assert next(iter(h.artifacts.items.values())).status is MentoringArtifactStatus.COMPLETED

    other = await h.session(hours=3)
    h.source.files = [MeetFile("VIDEO", "v2")]
    h.archive.fail = True
    await h.service.collect(other.id)
    h.clock.set(other.ends_at + timedelta(days=7, minutes=1))
    await h.service.sync()
    failed = [a for a in h.artifacts.items.values() if a.drive_file_id == "v2"]
    assert failed[0].status is MentoringArtifactStatus.FAILED


async def test_view_and_stream_permissions(h: Harness) -> None:
    session = await h.session()
    h.source.files = [MeetFile("VIDEO", "v1"), MeetFile("TRANSCRIPT", "t1")]
    await h.service.collect(session.id)
    student_user = h.student.user_id
    assert student_user is not None
    items = await h.service.list_for_user(student_user, session.id)
    assert len(items) == 2
    assert len(await h.service.list_for_user(h.mentor.account_id, session.id)) == 2
    assert len(await h.service.list_for_cohort(h.cohort_id, session.id)) == 2
    with pytest.raises(NotFoundError):
        await h.service.list_for_user(new_id(), session.id)  # 참여자가 아님

    video = next(a for a in items if a.artifact_type is MentoringArtifactType.VIDEO)
    doc = next(a for a in items if a.is_document)
    await h.service.open_for_user(student_user, session.id, video.id, "bytes=0-9")
    await h.service.open_for_cohort(h.cohort_id, session.id, doc.id, None)
    assert h.archive.streamed == [("v1", False, "bytes=0-9"), ("t1", True, None)]
    with pytest.raises(NotFoundError):
        await h.service.open_for_user(student_user, session.id, new_id(), None)


async def test_link_check_and_markdown(h: Harness) -> None:
    """서명 링크 전 확인과 스마트 메모 마크다운 (A68)."""
    session = await h.session()
    h.source.files = [MeetFile("VIDEO", "v1"), MeetFile("SUMMARY", "s1")]
    await h.service.collect(session.id)
    student_user = h.student.user_id
    assert student_user is not None
    items = await h.service.list_for_user(student_user, session.id)
    video = next(a for a in items if a.artifact_type is MentoringArtifactType.VIDEO)
    memo = next(a for a in items if a.artifact_type is MentoringArtifactType.SUMMARY)
    assert (await h.service.viewable_for_user(student_user, session.id, video.id)).id == video.id
    with pytest.raises(NotFoundError):
        await h.service.viewable_for_user(new_id(), session.id, video.id)  # 참여자가 아님
    artifact, markdown = await h.service.markdown_for_user(h.mentor.account_id, session.id, memo.id)
    assert (artifact.id, markdown) == (memo.id, "## s1")
    with pytest.raises(NotFoundError):
        await h.service.markdown_for_user(student_user, session.id, video.id)  # 영상은 없음


async def test_disabled_and_canceled(h: Harness) -> None:
    session = await h.session()
    h.sessions.items[session.id].status = h.sessions.items[session.id].status.CANCELED
    h.source.files = [MeetFile("VIDEO", "v1")]
    assert await h.service.collect(session.id) == 0
    h.service._source = None
    assert not h.service.enabled
    assert await h.service.sync() == (0, 0)


async def test_transcript_entries_collected_once_with_service_names(h: Harness) -> None:
    """전사본을 수집하면 전사 항목을 받아 화자를 서비스 이름으로 바꾼다 (A69)."""
    session = await h.session()
    at = START + timedelta(minutes=5)
    h.source.files = [
        MeetFile("VIDEO", "v1", record_name="c1", started_at=START),
        MeetFile("TRANSCRIPT", "t1", record_name="c1", source_name="c1/transcripts/t"),
    ]
    h.source.lines["c1/transcripts/t"] = [
        MeetTranscriptLine("김멘토", "README를 봅시다", at, at + timedelta(seconds=4)),  # 실명
        MeetTranscriptLine("가 수강", "네", at + timedelta(seconds=5), None),  # 수강생
        MeetTranscriptLine("Guest", "안녕하세요", at + timedelta(seconds=9), None),  # 모름
    ]
    h.source.lines_fail = True  # 처음엔 실패 → 다음 수집에서 다시
    await h.service.collect(session.id)
    assert h.entries.items == []
    h.source.lines_fail = False
    await h.service.collect(session.id)
    await h.service.collect(session.id)  # 이미 받았으면 다시 받지 않는다
    assert h.source.line_calls == ["c1/transcripts/t"] * 2

    video, transcript = sorted(h.artifacts.items.values(), key=lambda a: a.drive_file_id)[::-1]
    assert (video.conference_record, video.started_at) == ("c1", START)
    student_user = h.student.user_id
    assert student_user is not None
    entries = await h.service.entries_for_user(student_user, session.id, transcript.id)
    assert [(e.sequence, e.speaker_name) for e in entries] == [
        (0, "멘토K"),  # 표시 이름(닉네임 선택)으로, 실명은 감춘다
        (1, "가수강"),
        (2, "Guest"),
    ]
    assert entries[0].meet_name == "김멘토"
    with pytest.raises(NotFoundError):
        await h.service.entries_for_user(student_user, session.id, video.id)  # 영상은 없음
    with pytest.raises(NotFoundError):
        await h.service.entries_for_user(new_id(), session.id, transcript.id)  # 참여자 아님


async def test_existing_files_get_conference_info(h: Harness) -> None:
    """회의 정보 없이 먼저 만든 파일은 다음 수집에서 채운다 (A69)."""
    session = await h.session()
    h.source.files = [MeetFile("VIDEO", "v1")]
    await h.service.collect(session.id)
    end = START + timedelta(minutes=40)
    h.source.files = [MeetFile("VIDEO", "v1", record_name="c1", started_at=START, ended_at=end)]
    await h.service.collect(session.id)
    (video,) = h.artifacts.items.values()
    assert (video.conference_record, video.started_at, video.ended_at) == ("c1", START, end)

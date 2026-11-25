"""Meet 녹화·전사·스마트 메모 수집·정리·열람 (decisions M19·M20·A53·A54, P13-2).

수집: 세션 공간의 회의 기록에서 생성이 끝난 파일만 가져와 PENDING으로 남긴다(세션·파일 유니크,
  멱등).
  - 파일 생성 이벤트를 받으면 그 세션을 바로 수집하고(작업), 1시간마다 종료 7일 이내 세션을 보완
    수집한다(M20).
정리: 공유 드라이브 `멘토링 녹화/과정명/N기/멘토 실명/YYYY-MM`(세션 시작일 KST)로 주최 계정을 대신해
  옮기고 이름·형식·크기를 채워 COMPLETED. 세션 종료 7일이 지나도 못 하면 FAILED.
열람: 담당 멘토·그 세션 수강생(1:1 신청자·팀원)·운영진(기수 범위)이 COMPLETED 파일을 본다.
  영상은 Range 그대로, 문서는 PDF로 내보내 중계한다.
Meet API가 알려 준 세션 파일만 다룬다(주최 계정의 다른 Drive 파일은 건드리지 않음).
"""

import logging
import uuid
from collections.abc import Iterable, Mapping
from datetime import timedelta
from typing import Protocol

from app.contexts.academy.domain.entities import Student
from app.contexts.educator.domain.profiles import Mentor
from app.contexts.identity.domain.entities import User
from app.contexts.mentoring.domain.artifact import MentoringArtifact
from app.contexts.mentoring.domain.enums import MentoringArtifactType, MentoringSessionStatus
from app.contexts.mentoring.domain.repositories import (
    MentoringArtifactRepository,
    MentoringRequestRepository,
    MentoringSessionRepository,
    TranscriptEntryRepository,
)
from app.contexts.mentoring.domain.session import MentoringSession
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.domain.transcript import (
    SPEAKER_MAX_LENGTH,
    TranscriptEntry,
    name_key,
    speaker_name,
)
from app.core.clock import Clock
from app.integrations.google.drive import DriveFile, DriveStream, DriveUnavailableError
from app.integrations.google.meet import MeetUnavailableError
from app.integrations.google.meet_events import MeetFile, MeetTranscriptLine
from app.shared.errors import NotFoundError
from app.shared.time import KST

logger = logging.getLogger(__name__)

COLLECT_WINDOW = timedelta(days=7)  # M20: 종료 7일 이내만 보완 수집, 그 뒤 정리 못 하면 FAILED
ROOT_NAME = "멘토링 녹화"


class MeetFileSource(Protocol):
    async def session_files(self, space_name: str) -> list[MeetFile]: ...
    async def transcript_lines(self, transcript_name: str) -> list[MeetTranscriptLine]:
        """전사 항목 (A69)."""
        ...


class TeamMembers(Protocol):
    async def list_by_ids(self, team_ids: list[uuid.UUID]) -> list[MentoringTeam]: ...


class DriveArchive(Protocol):
    async def ensure_folder(self, path: list[str]) -> str: ...
    async def move(self, file_id: str, folder_id: str) -> None: ...
    async def describe(self, file_id: str) -> DriveFile: ...
    async def stream(
        self, file_id: str, *, export_pdf: bool, range_header: str | None
    ) -> DriveStream: ...
    async def export_markdown(self, file_id: str) -> str:
        """Google 문서를 마크다운으로 내보낸다 (스마트 메모 패널, A68)."""
        ...


class CohortLabelLike(Protocol):
    @property
    def bootcamp_name(self) -> str: ...
    @property
    def cohort_number(self) -> int: ...


class CohortLabels(Protocol):
    """academy `AcademyCatalog`."""

    async def cohort_labels(
        self, cohort_ids: Iterable[uuid.UUID]
    ) -> Mapping[uuid.UUID, CohortLabelLike]: ...


class StudentLookup(Protocol):
    async def get_many(self, student_ids: list[uuid.UUID]) -> dict[uuid.UUID, Student]: ...


class MentorLookup(Protocol):
    async def get(self, mentor_id: uuid.UUID) -> Mentor | None: ...


class UserLookup(Protocol):
    async def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]: ...


class SessionAccess(Protocol):
    """mentoring `MentoringSessionQueries` (참여자·멘토 / 기수 범위 확인, 아니면 404)."""

    async def get_for_user(self, user_id: uuid.UUID, session_id: uuid.UUID) -> MentoringSession: ...
    async def get_for_cohort(
        self, cohort_id: uuid.UUID, session_id: uuid.UUID
    ) -> MentoringSession: ...


def _not_found() -> NotFoundError:
    return NotFoundError("파일을 찾을 수 없습니다.", code="artifact_not_found")


class ArtifactService:
    def __init__(
        self,
        *,
        sessions: MentoringSessionRepository,
        requests: MentoringRequestRepository,
        artifacts: MentoringArtifactRepository,
        access: SessionAccess,
        source: MeetFileSource | None,
        archive: DriveArchive | None,
        students: StudentLookup,
        cohorts: CohortLabels,
        mentors: MentorLookup,
        users: UserLookup,
        clock: Clock,
        entries: TranscriptEntryRepository | None = None,
        teams: TeamMembers | None = None,
    ) -> None:
        self._entries = entries
        self._teams = teams
        self._sessions = sessions
        self._requests = requests
        self._artifacts = artifacts
        self._access = access
        self._source = source
        self._archive = archive
        self._students = students
        self._cohorts = cohorts
        self._mentors = mentors
        self._users = users
        self._clock = clock

    @property
    def enabled(self) -> bool:
        return self._source is not None and self._archive is not None

    # ------------------------------------------------------------------ 수집·정리
    async def collect(self, session_id: uuid.UUID) -> int:
        """세션 파일을 수집하고 그 세션 것을 정리한다. 새로 수집한 파일 수 (Google 오류는 예외)."""
        added = await self._gather(session_id)
        await self._archive_all(
            [a for a in await self._artifacts.list_by_session(session_id) if a.needs_archive]
        )
        return added

    async def _gather(self, session_id: uuid.UUID) -> int:
        if self._source is None:
            return 0
        session = await self._sessions.get(session_id)
        if (
            session is None
            or session.google_space_name is None
            or session.status is MentoringSessionStatus.CANCELED
        ):
            return 0
        added = 0
        files = await self._source.session_files(session.google_space_name)
        for file in files:
            artifact = MentoringArtifact(
                session_id=session.id,
                drive_file_id=file.file_id,
                artifact_type=MentoringArtifactType(file.kind),
                conference_record=file.record_name or None,
                started_at=file.started_at,
                ended_at=file.ended_at,
            )
            if await self._artifacts.add_if_absent(artifact):
                added += 1
        await self._link_and_transcribe(session, files)
        return added

    async def _link_and_transcribe(self, session: MentoringSession, files: list[MeetFile]) -> None:
        """이전에 만든 파일의 회의 정보를 채우고, 문장이 없는 전사본의 전사 항목을 받는다 (A69).

        전사 항목을 못 받으면 다음 보완 수집에서 다시 한다(세션 종료 7일까지).
        """
        by_file = {a.drive_file_id: a for a in await self._artifacts.list_by_session(session.id)}
        for file in files:
            artifact = by_file.get(file.file_id)
            if artifact and artifact.link_conference(
                file.record_name or None, file.started_at, file.ended_at
            ):
                await self._artifacts.save(artifact)
        if self._entries is None or self._source is None:
            return
        transcripts = [
            (by_file[f.file_id], f.source_name)
            for f in files
            if f.kind == MentoringArtifactType.TRANSCRIPT.value
            and f.source_name
            and f.file_id in by_file
        ]
        done = await self._entries.artifacts_with_entries([a.id for a, _ in transcripts])
        aliases: dict[str, str] | None = None
        for artifact, source_name in transcripts:
            if artifact.id in done:
                continue
            try:
                lines = await self._source.transcript_lines(source_name)
            except MeetUnavailableError:
                logger.warning("전사 항목 수집 실패 (파일 %s), 다음 주기에 다시 한다", artifact.id)
                continue
            if aliases is None:
                aliases = await self._speaker_aliases(session)
            await self._entries.add_many(
                [
                    TranscriptEntry(
                        artifact_id=artifact.id,
                        sequence=i,
                        speaker_name=speaker_name(line.meet_name, aliases),
                        meet_name=line.meet_name.strip()[:SPEAKER_MAX_LENGTH],
                        text=line.text,
                        started_at=line.started_at,
                        ended_at=line.ended_at,
                    )
                    for i, line in enumerate(lines)
                ]
            )

    async def _speaker_aliases(self, session: MentoringSession) -> dict[str, str]:
        """Meet 이름 → 서비스 이름 (A69): 멘토 실명·닉네임 → 표시 이름, 참여 수강생 → 이름."""
        aliases: dict[str, str] = {}
        request = await self._requests.get(session.request_id)
        student_ids: list[uuid.UUID] = [request.requester_id] if request else []
        if request and request.team_id and self._teams is not None:
            teams = await self._teams.list_by_ids([request.team_id])
            student_ids = [m for t in teams for m in t.member_ids] or student_ids
        for student in (await self._students.get_many(student_ids)).values():
            aliases[name_key(student.name)] = student.name
        mentor = await self._mentors.get(session.mentor_id)
        if mentor is not None:
            user = (await self._users.get_many([mentor.account_id])).get(mentor.account_id)
            real = user.name if user else ""
            shown = mentor.display_name(real)
            for name in (real, mentor.nickname or ""):
                if name.strip():
                    aliases[name_key(name)] = shown
        return aliases

    async def sync(self) -> tuple[int, int]:
        """1시간마다: 종료 7일 이내 세션 보완 수집 + 남은 정리 (새로 수집 수, 정리 수)."""
        if not self.enabled:
            return 0, 0
        now = self._clock.now()
        collected = 0
        for session in await self._sessions.list_recent_with_space(now - COLLECT_WINDOW, now):
            try:
                collected += await self._gather(session.id)
            except MeetUnavailableError:
                logger.warning("녹화 수집 실패 (세션 %s), 다음 주기에 다시 한다", session.id)
        archived = await self._archive_all(await self._artifacts.list_pending())
        return collected, archived

    async def _archive_all(self, pending: list[MentoringArtifact]) -> int:
        if self._archive is None or not pending:
            return 0
        done = 0
        now = self._clock.now()
        for artifact in pending:
            session = await self._sessions.get(artifact.session_id)
            if session is None:
                continue
            try:
                folder = await self._archive.ensure_folder(await self._folder_path(session))
                await self._archive.move(artifact.drive_file_id, folder)
                info = await self._archive.describe(artifact.drive_file_id)
            except DriveUnavailableError:
                if session.ends_at + COLLECT_WINDOW < now:
                    artifact.failed()
                    await self._artifacts.save(artifact)
                    logger.warning("녹화 정리 포기 (파일 %s, 7일 지남)", artifact.id)
                continue
            artifact.archived(file_name=info.name, mime_type=info.mime_type, file_size=info.size)
            await self._artifacts.save(artifact)
            done += 1
        return done

    async def _folder_path(self, session: MentoringSession) -> list[str]:
        """과정명/N기/멘토 실명/YYYY-MM (A53)."""
        request = await self._requests.get(session.request_id)
        student = (
            (await self._students.get_many([request.requester_id])).get(request.requester_id)
            if request
            else None
        )
        label = (
            (await self._cohorts.cohort_labels([student.cohort_id])).get(student.cohort_id)
            if student
            else None
        )
        mentor = await self._mentors.get(session.mentor_id)
        user = (
            (await self._users.get_many([mentor.account_id])).get(mentor.account_id)
            if mentor
            else None
        )
        month = session.starts_at.astimezone(KST).strftime("%Y-%m")
        return [
            (label.bootcamp_name if label else "") or "미분류",
            f"{label.cohort_number}기" if label else "미분류",
            (user.name if user else "") or "미분류",
            month,
        ]

    # ------------------------------------------------------------------ 열람
    async def list_for_user(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[MentoringArtifact]:
        session = await self._access.get_for_user(user_id, session_id)
        return await self._viewable(session)

    async def list_for_cohort(
        self, cohort_id: uuid.UUID, session_id: uuid.UUID
    ) -> list[MentoringArtifact]:
        session = await self._access.get_for_cohort(cohort_id, session_id)
        return await self._viewable(session)

    async def open_for_user(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        artifact_id: uuid.UUID,
        range_header: str | None,
    ) -> tuple[MentoringArtifact, DriveStream]:
        session = await self._access.get_for_user(user_id, session_id)
        return await self._open(session, artifact_id, range_header)

    async def open_for_cohort(
        self,
        cohort_id: uuid.UUID,
        session_id: uuid.UUID,
        artifact_id: uuid.UUID,
        range_header: str | None,
    ) -> tuple[MentoringArtifact, DriveStream]:
        session = await self._access.get_for_cohort(cohort_id, session_id)
        return await self._open(session, artifact_id, range_header)

    async def viewable_for_user(
        self, user_id: uuid.UUID, session_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> MentoringArtifact:
        """참여자가 볼 수 있는 파일인지 확인한다 (재생 링크 발급 전, A68)."""
        session = await self._access.get_for_user(user_id, session_id)
        return await self._artifact_of(session, artifact_id)

    async def markdown_for_user(
        self, user_id: uuid.UUID, session_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> tuple[MentoringArtifact, str]:
        """스마트 메모(SUMMARY)를 마크다운으로 (저장 안 함, A68). 다른 종류는 없는 파일로 본다."""
        session = await self._access.get_for_user(user_id, session_id)
        artifact = await self._artifact_of(session, artifact_id)
        if artifact.artifact_type is not MentoringArtifactType.SUMMARY or self._archive is None:
            raise _not_found()
        return artifact, await self._archive.export_markdown(artifact.drive_file_id)

    async def _artifact_of(
        self, session: MentoringSession, artifact_id: uuid.UUID
    ) -> MentoringArtifact:
        artifact = await self._artifacts.get(artifact_id)
        if artifact is None or artifact.session_id != session.id or not artifact.is_viewable:
            raise _not_found()
        return artifact

    async def entries_for_user(
        self, user_id: uuid.UUID, session_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> list[TranscriptEntry]:
        """전사본(TRANSCRIPT)의 문장 (A68·A69). 다른 종류는 없는 파일로 본다."""
        session = await self._access.get_for_user(user_id, session_id)
        artifact = await self._artifact_of(session, artifact_id)
        if artifact.artifact_type is not MentoringArtifactType.TRANSCRIPT or self._entries is None:
            raise _not_found()
        return await self._entries.list_by_artifact(artifact.id)

    async def _viewable(self, session: MentoringSession) -> list[MentoringArtifact]:
        return [a for a in await self._artifacts.list_by_session(session.id) if a.is_viewable]

    async def _open(
        self, session: MentoringSession, artifact_id: uuid.UUID, range_header: str | None
    ) -> tuple[MentoringArtifact, DriveStream]:
        artifact = await self._artifacts.get(artifact_id)
        if (
            artifact is None
            or artifact.session_id != session.id
            or not artifact.is_viewable
            or self._archive is None
        ):
            raise _not_found()
        stream = await self._archive.stream(
            artifact.drive_file_id, export_pdf=artifact.is_document, range_header=range_header
        )
        return artifact, stream

"""멘토링 세션 저장·조회와 DB 제약 (A42·A43)."""

from datetime import datetime, timedelta
from typing import Any

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.mentoring.domain.enums import MentoringRequestStatus, MentoringSessionStatus
from app.contexts.mentoring.domain.request import MentoringRequest
from app.contexts.mentoring.domain.session import MentoringSession, SessionQuery
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.repositories import (
    TortoiseMentoringRequestRepository,
    TortoiseMentoringSessionRepository,
    TortoiseMentoringTeamRepository,
)
from app.shared.errors import ConflictError
from app.shared.ids import new_id
from app.shared.time import KST
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

sessions = TortoiseMentoringSessionRepository()
requests = TortoiseMentoringRequestRepository()
T = datetime(2026, 11, 20, 14, tzinfo=KST)


async def _approved(mentor_id: Any, requester_id: Any, team_id: Any = None) -> MentoringRequest:
    request = MentoringRequest(
        requester_id=requester_id,
        mentor_id=mentor_id,
        team_id=team_id,
        topic="리뷰",
        detail="내용",
        desired_times=[T],
        duration=60,
        status=MentoringRequestStatus.APPROVED,
    )
    await requests.add(request)
    return request


def _session(request: MentoringRequest, starts_at: datetime = T) -> MentoringSession:
    return MentoringSession(
        mentor_id=request.mentor_id,
        request_id=request.id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=request.duration),
        title="제목",
        topic=request.topic,
    )


async def test_session_round_trip_overlap_and_lists() -> None:
    cohort = await create_cohort()
    student, teammate = make_student(cohort_id=cohort.id), make_student(cohort_id=cohort.id)
    for s in (student, teammate):
        await TortoiseStudentRepository().add(s)
    mentor, other_mentor = await create_mentor(), await create_mentor()
    team = MentoringTeam(
        cohort_id=cohort.id, team_number=1, mentor_id=mentor.id, member_ids=[teammate.id]
    )
    await TortoiseMentoringTeamRepository().add(team)

    solo = _session(await _approved(mentor.id, student.id))
    await sessions.add(solo)
    stored = await sessions.get(solo.id)
    assert stored is not None
    assert (stored.status, stored.starts_at, stored.request_id) == (
        MentoringSessionStatus.SCHEDULED,
        T,
        solo.request_id,
    )

    # 같은 멘토의 겹치는 세션 → 409, 이어지는 세션은 허용
    with pytest.raises(ConflictError) as overlap:
        await sessions.add(
            _session(await _approved(mentor.id, student.id), T + timedelta(minutes=30))
        )
    assert overlap.value.code == "mentor_schedule_conflict"
    team_session = _session(
        await _approved(mentor.id, teammate.id, team.id), T + timedelta(hours=1)
    )
    await sessions.add(team_session)
    other = _session(await _approved(other_mentor.id, student.id))  # 다른 멘토는 같은 시각 가능
    await sessions.add(other)

    assert await sessions.count_for_pair(mentor.id, requester_id=student.id, team_id=None) == 1
    assert await sessions.count_for_pair(mentor.id, requester_id=None, team_id=team.id) == 1
    end = T + timedelta(hours=1)
    assert await sessions.has_participant_overlap(
        student_ids=[student.id], team_ids=[], starts_at=T, ends_at=end
    )
    assert not await sessions.has_participant_overlap(  # 팀원 1:1은 팀 세션과 별개
        student_ids=[teammate.id], team_ids=[], starts_at=T, ends_at=end
    )
    assert await sessions.has_participant_overlap(
        student_ids=[], team_ids=[team.id], starts_at=end, ends_at=end + timedelta(minutes=30)
    )

    mine, total = await sessions.list_for_participants(
        student_ids=[student.id], team_ids=[team.id], query=SessionQuery()
    )
    assert total == 3
    assert [s.id for s in mine] == [
        team_session.id,
        other.id,
        solo.id,
    ]  # 시작 최신순, 같으면 id 역순
    first_hour, _ = await sessions.list_for_participants(
        student_ids=[student.id],
        team_ids=[team.id],
        query=SessionQuery(starts_from=T, starts_before=T + timedelta(hours=1)),
    )
    assert {s.id for s in first_hour} == {solo.id, other.id}
    by_mentor, mentor_total = await sessions.list_for_mentor(mentor.id, SessionQuery(limit=1))
    assert (mentor_total, [s.id for s in by_mentor]) == (2, [team_session.id])
    _, cohort_total = await sessions.list_by_cohort(
        cohort.id, mentor_id=other_mentor.id, query=SessionQuery()
    )
    assert cohort_total == 1

    db = connections.get("default")
    await db.execute_query(  # 취소된 세션은 겹침 검사에서 빠진다
        "UPDATE mentoring_sessions SET status = 'CANCELED' WHERE id = ANY($1::uuid[])",
        [[str(solo.id), str(other.id)]],
    )
    await sessions.add(_session(await _approved(mentor.id, student.id), T - timedelta(minutes=30)))
    assert not await sessions.has_participant_overlap(
        student_ids=[student.id], team_ids=[], starts_at=T + timedelta(minutes=30), ends_at=end
    )
    for sql in ("status = 'DONE'", "recording_status = 'X'", "ends_at = starts_at"):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_sessions SET {sql} WHERE id = $1", [str(other.id)]
            )
    taken = await requests.get(other.request_id)
    assert taken is not None
    with pytest.raises(IntegrityError):  # 신청 하나에 세션 하나
        await sessions.add(_session(taken, T + timedelta(days=1)))


async def test_save_lock_and_busy() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    first = _session(await _approved(mentor.id, student.id))
    second = _session(await _approved(mentor.id, student.id), T + timedelta(hours=3))
    for s in (first, second):
        await sessions.add(s)

    locked = await sessions.lock_by_request(first.request_id)
    assert locked is not None
    assert locked.id == first.id
    assert (await sessions.get_by_request(new_id())) is None

    day_end = T + timedelta(hours=10)
    busy = await sessions.busy(mentor.id, T - timedelta(hours=1), day_end)
    assert [(i.start, i.end) for i in busy] == [
        (T, T + timedelta(hours=1)),
        (T + timedelta(hours=3), T + timedelta(hours=4)),
    ]
    without = await sessions.busy(mentor.id, T, day_end, exclude_request_id=second.request_id)
    assert len(without) == 1
    assert await sessions.busy(mentor.id, T + timedelta(hours=1), T + timedelta(hours=3)) == []

    locked.cancel()
    await sessions.save(locked)
    stored = await sessions.get(first.id)
    assert stored is not None
    assert stored.status is MentoringSessionStatus.CANCELED
    assert len(await sessions.busy(mentor.id, T, day_end)) == 1


async def test_list_pending_and_upcoming() -> None:
    cohort, other_cohort = await create_cohort(), await create_cohort()
    student = make_student(cohort_id=cohort.id)
    outsider = make_student(cohort_id=other_cohort.id)
    for s in (student, outsider):
        await TortoiseStudentRepository().add(s)
    mentor = await create_mentor()
    team = MentoringTeam(
        cohort_id=cohort.id, team_number=1, mentor_id=mentor.id, member_ids=[student.id]
    )
    await TortoiseMentoringTeamRepository().add(team)

    def pending(requester: Any, team_id: Any = None) -> MentoringRequest:
        return MentoringRequest(
            requester_id=requester,
            mentor_id=mentor.id,
            team_id=team_id,
            topic="리뷰",
            detail="내용",
            desired_times=[T],
            duration=60,
        )

    solo, team_request, elsewhere = (
        pending(student.id),
        pending(student.id, team.id),
        pending(outsider.id),
    )
    for r in (solo, team_request, elsewhere):
        await requests.add(r)

    def ids(items: list[MentoringRequest]) -> set[Any]:
        return {r.id for r in items}

    assert ids(await requests.list_pending(mentor_id=mentor.id)) == ids(
        [solo, team_request, elsewhere]
    )
    assert ids(await requests.list_pending(mentor_id=mentor.id, cohort_id=cohort.id)) == ids(
        [solo, team_request]
    )
    assert ids(await requests.list_pending(team_ids=[team.id], requester_ids=[student.id])) == ids(
        [team_request]
    )
    assert ids(await requests.list_pending(requester_ids=[student.id], solo=True)) == ids([solo])

    past = _session(await _approved(mentor.id, student.id), T - timedelta(days=1))
    future = _session(await _approved(mentor.id, student.id), T + timedelta(hours=2))
    team_future = _session(await _approved(mentor.id, student.id, team.id), T + timedelta(hours=4))
    for session in (past, future, team_future):
        await sessions.add(session)
    upcoming = await sessions.list_upcoming(T, mentor_id=mentor.id)
    assert [s.id for s in upcoming] == [future.id, team_future.id]
    assert [s.id for s in await sessions.list_upcoming(T, solo=True)] == [future.id]


async def test_meet_space_queries() -> None:
    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    past = _session(await _approved(mentor.id, student.id), T - timedelta(days=1))
    upcoming = _session(await _approved(mentor.id, student.id), T + timedelta(hours=2))
    canceled = _session(await _approved(mentor.id, student.id), T + timedelta(hours=4))
    for session in (past, upcoming, canceled):
        await sessions.add(session)
    assert [s.id for s in await sessions.list_needing_space(T)] == [upcoming.id, canceled.id]

    locked = await sessions.lock(canceled.id)
    assert locked is not None
    locked.attach_space("spaces/abc", "https://meet.google.com/abc")
    locked.cancel()
    await sessions.save(locked)
    assert [s.id for s in await sessions.list_needing_space(T)] == [upcoming.id]
    assert [s.id for s in await sessions.list_needing_close()] == [canceled.id]
    found = await sessions.get_by_space("spaces/abc")
    assert found is not None
    assert found.id == canceled.id
    assert await sessions.get_by_space("spaces/none") is None
    locked.space_closed()
    await sessions.save(locked)
    assert await sessions.list_needing_close() == []
    stored = await sessions.get(canceled.id)
    assert stored is not None
    assert (stored.google_space_name, stored.google_meet_url) == ("spaces/abc", None)


async def test_notes_unrecorded_and_overtime_constraint() -> None:
    from app.contexts.mentoring.domain.note import MentoringSessionNote
    from app.contexts.mentoring.infrastructure.repositories import (
        TortoiseMentoringSessionNoteRepository,
    )

    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    started = _session(await _approved(mentor.id, student.id), T - timedelta(hours=2))
    recorded = _session(await _approved(mentor.id, student.id), T - timedelta(hours=5))
    upcoming = _session(await _approved(mentor.id, student.id), T + timedelta(hours=2))
    for session in (started, recorded, upcoming):
        await sessions.add(session)
    recorded.submit_completed(duration=60, topic="주제", summary="요약", now=T)
    await sessions.save(recorded)
    items, total = await sessions.list_unrecorded(cohort.id, before=T, limit=10, offset=0)
    assert (total, [s.id for s in items]) == (1, [started.id])
    stored = await sessions.get(recorded.id)
    assert stored is not None
    assert (stored.status, stored.record_duration_minutes, stored.body) == (
        MentoringSessionStatus.COMPLETED,
        60,
        "요약",
    )

    notes = TortoiseMentoringSessionNoteRepository()
    note = MentoringSessionNote(session_id=started.id, body="메모")
    await notes.add(note)
    note.rewrite("고친 메모")
    await notes.save(note)
    found = await notes.get_by_session(started.id)
    assert found is not None
    assert found.body == "고친 메모"
    with pytest.raises(IntegrityError):  # 세션당 하나
        await notes.add(MentoringSessionNote(session_id=started.id, body="두 번째"))
    db = connections.get("default")
    with pytest.raises(IntegrityError):
        await db.execute_query(
            "UPDATE mentoring_session_notes SET body = '' WHERE id = $1", [str(note.id)]
        )


async def test_artifact_repository_and_constraints() -> None:
    from app.contexts.mentoring.domain.artifact import MentoringArtifact
    from app.contexts.mentoring.domain.enums import MentoringArtifactType
    from app.contexts.mentoring.infrastructure.repositories import (
        TortoiseMentoringArtifactRepository,
    )

    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    session = _session(await _approved(mentor.id, student.id))
    await sessions.add(session)
    artifacts = TortoiseMentoringArtifactRepository()
    video = MentoringArtifact(
        session_id=session.id, drive_file_id="file-1", artifact_type=MentoringArtifactType.VIDEO
    )
    assert await artifacts.add_if_absent(video)
    duplicate = MentoringArtifact(
        session_id=session.id, drive_file_id="file-1", artifact_type=MentoringArtifactType.VIDEO
    )
    assert not await artifacts.add_if_absent(duplicate)  # 같은 세션·파일은 하나
    assert [a.id for a in await artifacts.list_pending()] == [video.id]
    video.archived(file_name="녹화.mp4", mime_type="video/mp4", file_size=1024)
    await artifacts.save(video)
    stored = await artifacts.get(video.id)
    assert stored is not None
    assert (stored.file_name, stored.file_size) == ("녹화.mp4", 1024)
    assert await artifacts.list_pending() == []
    assert [a.id for a in await artifacts.list_by_session(session.id)] == [video.id]
    db = connections.get("default")
    for sql in ("artifact_type = 'AUDIO'", "status = 'DONE'", "file_name = NULL"):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_artifacts SET {sql} WHERE id = $1", [str(video.id)]
            )


async def test_settlement_repository_and_constraints() -> None:
    from datetime import date

    from app.contexts.mentoring.domain.enums import (
        MentoringSettlementPolicy,
        MentoringSettlementStatus,
        PayUnit,
        SettlementItemType,
    )
    from app.contexts.mentoring.domain.settlement import MentoringSettlement, SettlementItem
    from app.contexts.mentoring.infrastructure.repositories import (
        TortoiseMentoringSettlementRepository,
    )

    cohort = await create_cohort()
    student = make_student(cohort_id=cohort.id)
    await TortoiseStudentRepository().add(student)
    mentor = await create_mentor()
    done = _session(await _approved(mentor.id, student.id), T - timedelta(days=1))
    pending = _session(await _approved(mentor.id, student.id), T - timedelta(hours=3))
    for session in (done, pending):
        await sessions.add(session)
    done.submit_completed(duration=60, topic="주제", summary="요약", now=T)
    await sessions.save(done)
    settleable = await sessions.list_settleable(cohort.id, before=T)
    assert [s.id for s in settleable] == [done.id]
    _, unrecorded = await sessions.list_unrecorded(
        cohort.id, before=T, limit=10, offset=0, mentor_id=mentor.id
    )
    assert unrecorded == 1

    repo = TortoiseMentoringSettlementRepository()

    def item(session_id: Any) -> SettlementItem:
        return SettlementItem(
            session_id=session_id,
            cohort_id=cohort.id,
            item_type=SettlementItemType.SESSION,
            settlement_policy=MentoringSettlementPolicy.ACTUAL_DURATION,
            billable_minutes=60,
            pay_unit=PayUnit.HOURLY,
            pay_rate=30000,
            amount=30000,
        )

    settlement = MentoringSettlement(
        mentor_id=mentor.id, cohort_id=cohort.id, settlement_month=date(2026, 11, 1)
    )
    settlement.replace_items([item(done.id)])
    await repo.save(settlement)
    stored = await repo.get_by_key(mentor.id, cohort.id, date(2026, 11, 1))
    assert stored is not None
    assert (stored.total_amount, [i.session_id for i in stored.items]) == (30000, [done.id])
    assert await repo.settled_session_ids([done.id], exclude_settlement_id=None) == {done.id}
    assert await repo.settled_session_ids([done.id], exclude_settlement_id=settlement.id) == set()
    stored.replace_items([])  # 다시 집계하면 명세를 통째로 바꾼다
    await repo.save(stored)
    assert (await repo.get(settlement.id)).items == []  # type: ignore[union-attr]

    other = MentoringSettlement(
        mentor_id=mentor.id, cohort_id=cohort.id, settlement_month=date(2026, 12, 1)
    )
    other.replace_items([item(done.id)])
    await repo.save(other)
    stored.replace_items([item(done.id)])
    with pytest.raises(IntegrityError):  # 세션은 한 번만 정산
        await repo.save(stored)

    other.close(T)
    await repo.save(other)
    assert [s.status for s in await repo.list_by_cohort(cohort.id, month=date(2026, 12, 1))] == [
        MentoringSettlementStatus.CLOSED
    ]
    db = connections.get("default")
    for sql in ("status = 'CLOSED', closed_at = NULL", "settlement_month = '2026-11-15'"):
        with pytest.raises(IntegrityError):
            await db.execute_query(
                f"UPDATE mentoring_settlements SET {sql} WHERE id = $1", [str(settlement.id)]
            )
    with pytest.raises(IntegrityError):
        await db.execute_query(
            "UPDATE mentoring_settlement_items SET pay_unit = 'MONTHLY' WHERE settlement_id = $1",
            [str(other.id)],
        )

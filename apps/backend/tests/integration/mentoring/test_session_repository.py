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

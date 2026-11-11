"""멘토링 팀 저장과 DB 제약 (유니크·복합 FK·CASCADE)."""

import pytest
from tortoise import connections
from tortoise.exceptions import IntegrityError

from app.contexts.academy.infrastructure.repositories import TortoiseStudentRepository
from app.contexts.mentoring.domain.team import MentoringTeam
from app.contexts.mentoring.infrastructure.models import MentoringTeamMemberModel
from app.contexts.mentoring.infrastructure.repositories import TortoiseMentoringTeamRepository
from app.core.uow import UnitOfWork
from app.shared.errors import ConflictError
from tests.factories.academy import create_cohort, make_student
from tests.factories.educator import create_mentor

pytestmark = pytest.mark.integration

repo = TortoiseMentoringTeamRepository()


async def test_team_round_trip_members_and_constraints() -> None:
    cohort = await create_cohort()
    mentor = await create_mentor()
    students = [make_student(cohort_id=cohort.id) for _ in range(3)]
    for s in students:
        await TortoiseStudentRepository().add(s)
    a, b, c = (s.id for s in students)

    assert await repo.next_number(cohort.id) == 1
    team = MentoringTeam(cohort_id=cohort.id, team_number=1, mentor_id=mentor.id, member_ids=[a, b])
    await repo.add(team)
    assert await repo.next_number(cohort.id) == 2
    assert await repo.next_number((await create_cohort()).id) == 1  # 기수별 번호

    loaded = await repo.get(team.id)
    assert loaded is not None
    assert loaded.member_ids == [a, b]
    loaded.remove_member(a)
    loaded.add_member(c)
    loaded.rename("알파")
    await repo.save(loaded)
    reloaded = await repo.get(team.id)
    assert reloaded is not None
    assert (reloaded.member_ids, reloaded.name) == ([b, c], "알파")
    assert await repo.team_of_students([a, b, c]) == {b: team.id, c: team.id}

    # 다른 팀에 같은 수강생 → 409 (수강 등록당 한 팀, A41)
    other = MentoringTeam(cohort_id=cohort.id, team_number=2, mentor_id=mentor.id, member_ids=[b])
    with pytest.raises(ConflictError) as dup:
        async with UnitOfWork():  # 서비스처럼 트랜잭션 안에서 (팀 행도 함께 롤백)
            await repo.add(other)
    assert dup.value.code == "student_in_other_team"
    second = MentoringTeam(cohort_id=cohort.id, team_number=2, mentor_id=mentor.id, member_ids=[a])
    await repo.add(second)
    assert [t.team_number for t in await repo.list_by_cohort(cohort.id)] == [1, 2]
    assert {t.id for t in await repo.list_by_students([a, b])} == {team.id, second.id}
    assert {t.id for t in await repo.list_by_ids([second.id])} == {second.id}
    assert len(await repo.list_by_mentor(mentor.id)) == 2
    with pytest.raises(IntegrityError):  # (기수, 팀 번호) 유니크
        await connections.get("default").execute_query(
            "UPDATE mentoring_teams SET team_number = 1 WHERE id = $1", [str(second.id)]
        )

    # 팀을 지우면 팀원도 지워진다
    await repo.delete(team.id)
    assert await repo.get(team.id) is None
    assert await MentoringTeamMemberModel.filter(team_id=team.id).count() == 0

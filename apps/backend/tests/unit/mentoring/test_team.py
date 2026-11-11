"""멘토링 팀 도메인 (A39)."""

import pytest

from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.contexts.mentoring.domain.team import MentoringTeam
from app.shared.errors import BusinessRuleViolation, ConflictError
from app.shared.ids import new_id

pytestmark = pytest.mark.unit


def _team(**overrides: object) -> MentoringTeam:
    values: dict[str, object] = {
        "cohort_id": new_id(),
        "period_type": MentoringPeriodType.PROJECT_MENTORING,
        "team_number": 3,
        "mentor_id": new_id(),
    }
    values.update(overrides)
    return MentoringTeam(**values)  # type: ignore[arg-type]


def test_team_name_and_number() -> None:
    assert _team().label == "3팀"
    team = _team(name="  알파  ")
    assert team.label == "알파"
    team.rename("   ")
    assert team.name is None
    with pytest.raises(BusinessRuleViolation) as long_name:
        team.rename("가" * 51)
    assert long_name.value.code == "invalid_team_name"
    with pytest.raises(BusinessRuleViolation):
        _team(team_number=0)


def test_members_and_mentor() -> None:
    team = _team()
    first, second = new_id(), new_id()
    team.add_member(first)
    team.add_member(second)
    with pytest.raises(ConflictError):
        team.add_member(first)
    team.remove_member(first)
    assert team.member_ids == [second]
    with pytest.raises(BusinessRuleViolation):
        team.remove_member(first)
    mentor = new_id()
    team.assign_mentor(mentor)
    assert team.mentor_id == mentor

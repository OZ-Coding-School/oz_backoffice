"""멘토링 팀 (decisions M11·A39).

- 팀 번호는 기수×유형별로 매긴다. 담당 멘토가 고정되며 팀 신청은 담당 멘토에게만 한다.
- 담당 멘토는 그 기수·유형의 활성 배정이어야 하고 언제든 바꿀 수 있다(서비스 검사).
- 수강생은 같은 유형의 팀에 하나만 소속된다(DB 유니크).
  팀원은 그 기수 수강 중이어야 한다(서비스 검사).
- 팀원은 루트(팀)와 함께 저장한다.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.contexts.mentoring.domain.enums import MentoringPeriodType
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation, ConflictError

NAME_MAX_LENGTH = 50


def _clean_name(name: str | None) -> str | None:
    text = (name or "").strip()
    if len(text) > NAME_MAX_LENGTH:
        raise BusinessRuleViolation(
            f"팀 이름은 {NAME_MAX_LENGTH}자 이하여야 합니다.", code="invalid_team_name"
        )
    return text or None


@dataclass(kw_only=True, eq=False)
class MentoringTeam(AggregateRoot):
    cohort_id: uuid.UUID
    period_type: MentoringPeriodType
    team_number: int
    mentor_id: uuid.UUID
    name: str | None = None
    member_ids: list[uuid.UUID] = field(default_factory=list)  # 수강 등록(students.id), 넣은 순서
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.team_number < 1:
            raise BusinessRuleViolation("팀 번호는 1 이상입니다.", code="invalid_team_number")
        self.name = _clean_name(self.name)

    @property
    def label(self) -> str:
        return self.name or f"{self.team_number}팀"

    def rename(self, name: str | None) -> None:
        self.name = _clean_name(name)

    def assign_mentor(self, mentor_id: uuid.UUID) -> None:
        self.mentor_id = mentor_id

    def add_member(self, student_id: uuid.UUID) -> None:
        if student_id in self.member_ids:
            raise ConflictError("이미 이 팀의 팀원입니다.", code="already_team_member")
        self.member_ids.append(student_id)

    def remove_member(self, student_id: uuid.UUID) -> None:
        if student_id not in self.member_ids:
            raise BusinessRuleViolation("이 팀의 팀원이 아닙니다.", code="not_team_member")
        self.member_ids.remove(student_id)

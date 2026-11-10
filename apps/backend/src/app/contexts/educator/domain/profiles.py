"""멘토 프로필 (decisions A22, A28).

수강생에게 보이는 소개 정보다. 실명·연락처는 회원(identity)에 있다.
- 닉네임은 앞뒤 공백을 지우고 빈 값은 None으로 둔다. 표시 이름 NICKNAME은 닉네임이 있어야 한다.
- 길이: 닉네임 30자, 한 줄 소개 100자, 전문 분야 200자, 소개(마크다운) 10,000자.
- 사진은 비공개 버킷 `profiles/` 객체 키만 둔다. 바꾸거나 지우면 이전 객체는 커밋 후 지운다.
- 운영진(mentor.manage)이 비활성화·재활성화한다. 비활성 멘토는 새 기수 배정을 받지 못한다(A35·A36).
"""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.contexts.educator.domain.enums import DisplayNamePreference
from app.shared.domain import AggregateRoot
from app.shared.errors import BusinessRuleViolation

NICKNAME_MAX_LENGTH = 30
HEADLINE_MAX_LENGTH = 100
EXPERTISE_MAX_LENGTH = 200
INTRODUCTION_MAX_LENGTH = 10_000

PROFILE_FIELDS = frozenset(
    {"nickname", "display_name_preference", "headline", "introduction", "expertise"}
)


def _optional_text(value: str | None, *, limit: int, code: str, label: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > limit:
        raise BusinessRuleViolation(f"{label}은(는) {limit:,}자 이하여야 합니다.", code=code)
    return text


@dataclass(kw_only=True, eq=False)
class Mentor(AggregateRoot):
    user_id: uuid.UUID
    nickname: str | None = None
    display_name_preference: DisplayNamePreference = DisplayNamePreference.NAME
    headline: str | None = None
    introduction: str | None = None
    expertise: str | None = None
    profile_image_key: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.nickname = _optional_text(
            self.nickname, limit=NICKNAME_MAX_LENGTH, code="invalid_nickname", label="닉네임"
        )
        self.headline = _optional_text(
            self.headline, limit=HEADLINE_MAX_LENGTH, code="invalid_headline", label="한 줄 소개"
        )
        self.expertise = _optional_text(
            self.expertise, limit=EXPERTISE_MAX_LENGTH, code="invalid_expertise", label="전문 분야"
        )
        self.introduction = _optional_text(
            self.introduction,
            limit=INTRODUCTION_MAX_LENGTH,
            code="invalid_introduction",
            label="소개",
        )
        if self.display_name_preference is DisplayNamePreference.NICKNAME and not self.nickname:
            raise BusinessRuleViolation(
                "닉네임을 입력해야 닉네임으로 표시할 수 있습니다.", code="nickname_required"
            )

    def with_profile(self, changes: dict[str, object]) -> "Mentor":
        """프로필 항목만 바꾼 새 멘토(생성과 같은 검증)."""
        if not set(changes) <= PROFILE_FIELDS:
            raise BusinessRuleViolation("수정할 수 없는 항목입니다.", code="invalid_profile_field")
        return dataclasses.replace(self, **changes)  # type: ignore[arg-type]  # 허용 필드만 통과

    def display_name(self, real_name: str) -> str:
        """수강생에게 보이는 이름 (표시 이름 선택 반영)."""
        if self.display_name_preference is DisplayNamePreference.NICKNAME and self.nickname:
            return self.nickname
        return real_name

    def deactivate(self) -> None:
        if not self.is_active:
            raise BusinessRuleViolation(
                "이미 비활성화된 멘토입니다.", code="mentor_already_inactive"
            )
        self.is_active = False

    def activate(self) -> None:
        if self.is_active:
            raise BusinessRuleViolation("이미 활성화된 멘토입니다.", code="mentor_already_active")
        self.is_active = True

    def replace_image(self, key: str | None) -> str | None:
        """사진 키를 바꾸고 이전 키를 돌려준다(커밋 후 객체 삭제용)."""
        previous, self.profile_image_key = self.profile_image_key, key
        return previous if previous != key else None

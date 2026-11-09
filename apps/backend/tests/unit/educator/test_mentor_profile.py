from typing import Any

import pytest

from app.contexts.educator.application.mentor_profiles import is_image
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.educator.domain.profiles import Mentor
from app.shared.errors import BusinessRuleViolation
from app.shared.ids import new_id

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
WEBP = b"RIFF\x00\x00\x00\x00WEBP"


def test_profile_text_is_trimmed_and_blank_becomes_none() -> None:
    mentor = Mentor(user_id=new_id(), nickname="  오즈 ", headline="  ", introduction="\n# 소개\n")
    assert (mentor.nickname, mentor.headline, mentor.introduction) == ("오즈", None, "# 소개")


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"nickname": "가" * 31}, "invalid_nickname"),
        ({"headline": "가" * 101}, "invalid_headline"),
        ({"expertise": "가" * 201}, "invalid_expertise"),
        ({"introduction": "가" * 10_001}, "invalid_introduction"),
        ({"display_name_preference": DisplayNamePreference.NICKNAME}, "nickname_required"),
        ({"profile_image_key": "profiles/x.png"}, "invalid_profile_field"),
    ],
)
def test_profile_validation(changes: dict[str, Any], code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        Mentor(user_id=new_id()).with_profile(changes)
    assert exc.value.code == code


def test_nickname_display_and_boundaries() -> None:
    mentor = Mentor(user_id=new_id()).with_profile(
        {
            "nickname": "가" * 30,
            "display_name_preference": DisplayNamePreference.NICKNAME,
            "introduction": "가" * 10_000,
        }
    )
    assert mentor.display_name_preference is DisplayNamePreference.NICKNAME
    with pytest.raises(BusinessRuleViolation):  # 닉네임으로 표시 중에 닉네임을 비울 수 없다
        mentor.with_profile({"nickname": None})


def test_replace_image_returns_previous_key() -> None:
    mentor = Mentor(user_id=new_id())
    assert mentor.replace_image("profiles/a.png") is None
    assert mentor.replace_image("profiles/b.png") == "profiles/a.png"
    assert mentor.replace_image(None) == "profiles/b.png"
    assert mentor.profile_image_key is None


@pytest.mark.parametrize(
    ("head", "content_type", "expected"),
    [
        (PNG, "image/png", True),
        (JPEG, "image/jpeg", True),
        (WEBP, "image/webp", True),
        (PNG, "image/jpeg", False),  # 타입과 내용이 다르면 거부
        (b"%PDF-1.7\n" + b"0" * 3, "image/png", False),
        (b"RIFF\x00\x00\x00\x00WAVE", "image/webp", False),
        (PNG, "image/gif", False),
    ],
)
def test_is_image(head: bytes, content_type: str, expected: bool) -> None:
    assert is_image(head, content_type) is expected

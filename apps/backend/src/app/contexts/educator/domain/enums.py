from enum import StrEnum


class EducatorType(StrEnum):
    MENTOR = "MENTOR"  # 멘토
    INSTRUCTOR = "INSTRUCTOR"  # 강사


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"  # 작성 중 (계약서 없어도 됨, A23)
    ACTIVE = "ACTIVE"  # 체결
    ENDED = "ENDED"  # 기간 만료
    TERMINATED = "TERMINATED"  # 중도 해지


class DisplayNamePreference(StrEnum):
    """수강생에게 보일 이름 (A22). NICKNAME은 닉네임이 있을 때만 고를 수 있다."""

    NAME = "NAME"  # 실명
    NICKNAME = "NICKNAME"  # 닉네임

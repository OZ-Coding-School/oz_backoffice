from enum import StrEnum


class MentoringPeriodType(StrEnum):
    PROJECT_MENTORING = "PROJECT_MENTORING"  # 프로젝트 기간 멘토링
    REGULAR_MENTORING = "REGULAR_MENTORING"  # 정기(평시) 멘토링


class MentoringSettlementPolicy(StrEnum):
    STUDENT_REQUEST = "STUDENT_REQUEST"  # 수강생 요청 시간 기준
    ACTUAL_DURATION = "ACTUAL_DURATION"  # 실제 진행 시간 기준


class PayUnit(StrEnum):
    HOURLY = "HOURLY"  # 시급
    PER_SESSION = "PER_SESSION"  # 회당
    MONTHLY = "MONTHLY"  # 월정액 (멘토링 배정에는 쓰지 않음, M30)
    LUMP_SUM = "LUMP_SUM"  # 총액 (멘토링 배정에는 쓰지 않음, M30)


class CohortMentorDeactivationReason(StrEnum):
    EXPIRED = "EXPIRED"  # 종료일 경과 (매일 작업)
    MANUAL = "MANUAL"  # 운영진 비활성화(삭제)
    MENTOR_DEACTIVATED = "MENTOR_DEACTIVATED"  # 멘토 비활성화로 함께 비활성화


class UnavailableRepeat(StrEnum):
    """멘토 불가 시간 반복 규칙 (A37)."""

    ONCE = "ONCE"  # 일회성
    DAILY = "DAILY"  # 매일
    WEEKLY = "WEEKLY"  # 매주 (요일 여러 개)

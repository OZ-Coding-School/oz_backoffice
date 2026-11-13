from enum import StrEnum


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


class MentoringBalanceTransactionType(StrEnum):
    """시간 계좌 원장 유형 (M9·M10)."""

    STAFF_GRANT = "STAFF_GRANT"  # 운영진 지급: total += d
    STAFF_ADJUST = "STAFF_ADJUST"  # 운영진 조정(±): total += d
    HOLD = "HOLD"  # 신청: held += d
    RELEASE = "RELEASE"  # 승인 전 반려·취소: held -= d
    USING = "USING"  # 승인: held -= d, used += d
    REFUND = "REFUND"  # 승인 후 취소·노쇼·짧게 진행: used -= d
    OVERTIME = "OVERTIME"  # 신청보다 길게 진행(A53): used += d (잔여에서)


class MentoringRequestStatus(StrEnum):
    PENDING = "PENDING"  # 대기 (시간 보류)
    APPROVED = "APPROVED"  # 멘토 승인 (세션 생성)
    REJECTED = "REJECTED"  # 멘토 반려
    CANCELED = "CANCELED"  # 취소 (변경도 취소 후 새 신청)


class MentoringSessionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"  # 예정
    IN_PROGRESS = "IN_PROGRESS"  # 진행 중 (Meet 회의 시작, P12)
    COMPLETED = "COMPLETED"  # 완료
    NO_SHOW = "NO_SHOW"  # 노쇼
    CANCELED = "CANCELED"  # 취소


class RecordingStatus(StrEnum):
    """Meet 자동 녹화 상태 (P12·P13에서 갱신)."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    ENDED = "ENDED"
    FILE_GENERATED = "FILE_GENERATED"
    FAILED = "FAILED"


class MentoringArtifactType(StrEnum):
    VIDEO = "VIDEO"  # 녹화 영상 (mp4)
    TRANSCRIPT = "TRANSCRIPT"  # 전사본 (Google 문서)
    SUMMARY = "SUMMARY"  # 스마트 메모 요약 (Google 문서)


class MentoringArtifactStatus(StrEnum):
    PENDING = "PENDING"  # 수집됨, 정리 전
    PROCESSING = "PROCESSING"  # (예비)
    COMPLETED = "COMPLETED"  # 폴더 정리·메타데이터 완료, 열람 가능
    FAILED = "FAILED"  # 7일 동안 정리하지 못함

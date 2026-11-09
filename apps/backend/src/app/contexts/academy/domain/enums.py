from enum import StrEnum


class HRDNetTrainType(StrEnum):
    KDT = "KDT"  # K-Digital Training
    KDC = "KDC"  # K-Digital 기초 역량 훈련


class WeekendSeType(StrEnum):
    WEEKEND = "WEEKEND"
    WEEKDAY = "WEEKDAY"
    HYBRID = "HYBRID"


class DayNightSeType(StrEnum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    HYBRID = "HYBRID"


class CohortStatus(StrEnum):
    PLANNED = "PLANNED"  # 모집/준비
    ONGOING = "ONGOING"  # 진행 중
    ENDED = "ENDED"  # 종료
    INACTIVE = "INACTIVE"  # 비활성
    ARCHIVED = "ARCHIVED"  # 보관 (목록에서 숨김)


class EnrollmentStatus(StrEnum):
    ENROLLED = "ENROLLED"  # 수강 중
    COMPLETED = "COMPLETED"  # 수료
    DROPPED = "DROPPED"  # 중도포기
    EARLY_EMPLOYED = "EARLY_EMPLOYED"  # 조기취업
    TRANSFERRED = "TRANSFERRED"  # 기수 이동


class StudentStatus(StrEnum):
    """HRD-Net 상태 (Airtable `HRD상태`를 매핑, roster.py)."""

    REGISTERED = "REGISTERED"
    TRAINING = "TRAINING"
    COMPLETED = "COMPLETED"
    COMPLETED_80_PERCENT = "COMPLETED_80_PERCENT"
    COMPLETED_AND_EMPLOYED = "COMPLETED_AND_EMPLOYED"
    EARLY_EMPLOYED = "EARLY_EMPLOYED"
    WITHDRAWAL = "WITHDRAWAL"
    DROPPED_OUT = "DROPPED_OUT"
    LEAVE = "LEAVE"
    EXPELLED = "EXPELLED"
    UNKNOWN = "UNKNOWN"  # 확인필요·미입력·알 수 없는 값


class RosterSyncTrigger(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class RosterSyncScope(StrEnum):
    ALL = "ALL"
    BOOTCAMP = "BOOTCAMP"
    COHORT = "COHORT"


class RosterSyncStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

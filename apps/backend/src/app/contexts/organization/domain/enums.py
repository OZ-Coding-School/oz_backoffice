from enum import StrEnum


class EmploymentType(StrEnum):
    REGULAR = "REGULAR"  # 정규직
    CONTRACT = "CONTRACT"  # 사내 계약직
    INTERN = "INTERN"  # 인턴
    PART_TIME_JOB = "PART_TIME_JOB"  # 아르바이트
    FREELANCER = "FREELANCER"  # 프리랜서 계약직
    DAILY = "DAILY"  # 일용 계약직


class StaffRole(StrEnum):
    MANAGER = "MANAGER"  # 운영 매니저
    ASSISTANT = "ASSISTANT"  # 조교

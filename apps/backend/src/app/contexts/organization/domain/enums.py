from enum import StrEnum


class EmploymentType(StrEnum):
    REGULAR = "REGULAR"  # 정규직
    CONTRACT = "CONTRACT"  # 사내 계약직
    INTERN = "INTERN"  # 인턴
    PART_TIME_JOB = "PART_TIME_JOB"  # 아르바이트
    FREELANCER = "FREELANCER"  # 프리랜서 계약직
    DAILY = "DAILY"  # 일용 계약직


class AssignmentScope(StrEnum):
    """직위의 담당 방식 (decisions A62). 직위에 값이 없으면 담당이 없다."""

    COURSE = "COURSE"  # 소속 팀의 과정을 여러 개 (운영 매니저)
    COHORT = "COHORT"  # 소속 팀 과정의 기수 하나 (조교)


class DataScope(StrEnum):
    """직위의 데이터 범위 (A87): 기수에 속한 엔터티에 미치는 범위."""

    ASSIGNED = "ASSIGNED"  # 담당자로 배정된 과정·기수만
    ALL = "ALL"  # 모든 과정·기수


class StaffRole(StrEnum):
    MANAGER = "MANAGER"  # 운영 매니저
    ASSISTANT = "ASSISTANT"  # 조교


class EmployeeRegistrationStatus(StrEnum):
    PENDING = "PENDING"  # 승인 대기 (신청자가 수정 가능)
    APPROVED = "APPROVED"  # 승인 (직원·담당자 생성됨)
    REJECTED = "REJECTED"  # 반려 (다시 신청 가능)

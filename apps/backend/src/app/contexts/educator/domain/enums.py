from enum import StrEnum


class ContractType(StrEnum):
    """계약 종류 (A109①). 멘토 FK는 멘토 계약, 강사 FK는 강사 계약만 쓴다."""

    MENTOR = "MENTOR"  # 멘토
    INSTRUCTOR = "INSTRUCTOR"  # 강사
    SW = "SW"  # 소프트웨어
    EQUIPMENT = "EQUIPMENT"  # 장비
    OTHER = "OTHER"  # 기타

    @property
    def is_educator(self) -> bool:
        """멘토·강사 계약: 당사자 휴대폰 필수(가입 매칭), 업체 칸 없음"""
        return self in (ContractType.MENTOR, ContractType.INSTRUCTOR)


class ContractStatus(StrEnum):
    """계약 상태 (A109③)."""

    DRAFT = "DRAFT"  # 초안 (계약서 없어도 됨)
    IN_PROGRESS = "IN_PROGRESS"  # 계약 진행 중 (계약서 필수)
    SIGNED = "SIGNED"  # 계약 완료, 시작일 전
    ACTIVE = "ACTIVE"  # 이행 중
    ENDED = "ENDED"  # 정상 종료
    CANCELED = "CANCELED"  # 완료 전 취소
    TERMINATED = "TERMINATED"  # 완료 후 해지


class SettlementType(StrEnum):
    """계약 정산 유형 (A109④)."""

    FIXED = "FIXED"  # 정액: 총액 필수
    UNIT_PRICE = "UNIT_PRICE"  # 단가: 단가·단가 기준 필수
    ACTUAL_COST = "ACTUAL_COST"  # 실비: 한도액 선택


class PriceUnit(StrEnum):
    """단가 기준 (A109④)."""

    HOURLY = "HOURLY"  # 시간
    PER_SESSION = "PER_SESSION"  # 회
    DAILY = "DAILY"  # 일
    MONTHLY = "MONTHLY"  # 월
    PER_ITEM = "PER_ITEM"  # 건


# 멘토 계약이 쓸 수 있는 단가 기준 (멘토링 정산이 계산할 수 있는 것, A109⑩)
MENTOR_PRICE_UNITS = frozenset({PriceUnit.HOURLY, PriceUnit.PER_SESSION})


class VatType(StrEnum):
    INCLUDED = "INCLUDED"  # 부가세 포함
    EXCLUDED = "EXCLUDED"  # 부가세 별도
    NOT_APPLICABLE = "NOT_APPLICABLE"  # 해당 없음


class MentoringTimeBasis(StrEnum):
    """멘토 계약의 멘토링 정산 시간 기준 (A109④, 배정의 정산 기준과 같은 뜻)."""

    STUDENT_REQUEST = "STUDENT_REQUEST"  # 신청 시간
    ACTUAL_DURATION = "ACTUAL_DURATION"  # 실제 진행 시간


class TerminationReason(StrEnum):
    """해지 사유 (A109③)."""

    TERMINATED_BY_FAULT = "TERMINATED_BY_FAULT"  # 귀책 사유
    TERMINATED_BY_MUTUAL_AGREEMENT = "TERMINATED_BY_MUTUAL_AGREEMENT"  # 합의
    TERMINATED_BY_UNILATERAL = "TERMINATED_BY_UNILATERAL"  # 일방적 해지


class DisplayNamePreference(StrEnum):
    """수강생에게 보일 이름 (A22). NICKNAME은 닉네임이 있을 때만 고를 수 있다."""

    NAME = "NAME"  # 실명
    NICKNAME = "NICKNAME"  # 닉네임

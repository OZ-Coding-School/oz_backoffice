from enum import StrEnum


class AccountType(StrEnum):
    """계정 종류 (decisions A61·A65). 한 계정은 수강생·멘토·운영진 중 하나다.

    수강생·멘토는 이메일 가입 유형으로 정하고, 승인 전 재신청에서만 바뀐다.
    운영진은 회사 Google 로그인·CLI 최고 관리자로 만든다.
    """

    STUDENT = "STUDENT"  # 수강생
    MENTOR = "MENTOR"  # 멘토
    STAFF = "STAFF"  # 운영진


class UserApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SocialLoginProvider(StrEnum):
    KAKAO = "KAKAO"
    GOOGLE = "GOOGLE"
    NAVER = "NAVER"


class MemberSignupType(StrEnum):
    STUDENT = "STUDENT"  # 수강생
    MENTOR = "MENTOR"  # 멘토


class MemberSignupStatus(StrEnum):
    PENDING = "PENDING"  # 승인 대기
    APPROVED = "APPROVED"  # 승인 (자동 또는 운영진)
    REJECTED = "REJECTED"  # 반려 (새로 신청 가능)


class SignupMatchResult(StrEnum):
    MATCHED = "MATCHED"  # 명단·계약과 이름 + 휴대폰 일치 (자동 승인)
    NO_MATCH = "NO_MATCH"  # 일치 없음
    AMBIGUOUS = "AMBIGUOUS"  # 여러 사람과 애매하게 일치


def member_account_type(signup_type: MemberSignupType) -> AccountType:
    """가입 유형에 맞는 계정 종류 (A65)."""
    return AccountType.STUDENT if signup_type is MemberSignupType.STUDENT else AccountType.MENTOR

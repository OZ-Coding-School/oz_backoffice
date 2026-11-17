from enum import StrEnum


class AccountType(StrEnum):
    """계정 종류. 가입 경로로 정해지고 바뀌지 않는다 (decisions A61)."""

    MEMBER = "MEMBER"  # 수강생·멘토 (이메일·비밀번호 가입)
    STAFF = "STAFF"  # 운영진 (회사 Google 로그인, CLI 최고 관리자)


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

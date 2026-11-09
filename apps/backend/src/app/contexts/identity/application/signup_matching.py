"""가입 자동 매칭 (decisions A6·A31).

- 수강생: 신청한 기수 안에서 이름 + 휴대폰이 같고 수강 중·원천 존재·미가입인 명단이 정확히 1건이면
  그 명단을 회원에 연결하고 STUDENT 역할(그 기수 범위)을 준다 → MATCHED.
  0건 → NO_MATCH, 2건 이상(같은 기수에 중복 명단) → AMBIGUOUS.
- 멘토: 이름 + 휴대폰이 같은 유형 MENTOR·미연결 계약이 1건 이상이면(계약 상태 무관) 멘토 프로필을
  만들고 모두 연결한다 → MATCHED. 없으면 NO_MATCH. MENTOR 역할은 멘토 배정(P8)에서 준다(A17).
다른 컨텍스트 서비스는 가입 서비스의 트랜잭션 안에서 실행된다.
"""

import uuid
from typing import Protocol

from app.contexts.academy.application.student_claims import ClaimOutcome
from app.contexts.access.domain.catalog import STUDENT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.educator.application.mentor_onboarding import MentorMatch
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import MemberSignupType, SignupMatchResult
from app.contexts.identity.domain.signup import MemberSignup


class StudentClaimer(Protocol):
    """academy `StudentClaims`."""

    async def claim_in_cohort(
        self, cohort_id: uuid.UUID, *, name: str, phone_number: str, user_id: uuid.UUID
    ) -> ClaimOutcome: ...


class MentorLinker(Protocol):
    """educator `MentorOnboarding`."""

    async def link_contracts(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        phone_number: str,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
    ) -> MentorMatch: ...


class RoleGranter(Protocol):
    """access `RoleAssignmentService`."""

    async def grant(
        self,
        user_id: uuid.UUID,
        role_code: str,
        scope_type: RoleScopeType,
        scope_id: uuid.UUID | None = None,
    ) -> bool: ...


class SignupMatcher:
    def __init__(
        self, *, students: StudentClaimer, mentors: MentorLinker, roles: RoleGranter
    ) -> None:
        self._students = students
        self._mentors = mentors
        self._roles = roles

    async def match(self, user: User, signup: MemberSignup) -> SignupMatchResult:
        if user.phone_number is None:  # 가입은 SMS 인증을 거치므로 항상 있다
            return SignupMatchResult.NO_MATCH
        if signup.signup_type is MemberSignupType.STUDENT:
            return await self._match_student(user, signup, user.phone_number)
        return await self._match_mentor(user, signup, user.phone_number)

    async def _match_student(
        self, user: User, signup: MemberSignup, phone_number: str
    ) -> SignupMatchResult:
        if signup.requested_cohort_id is None:
            return SignupMatchResult.NO_MATCH
        outcome = await self._students.claim_in_cohort(
            signup.requested_cohort_id, name=user.name, phone_number=phone_number, user_id=user.id
        )
        if outcome.student_id is None:
            return (
                SignupMatchResult.AMBIGUOUS
                if outcome.candidate_count > 1
                else SignupMatchResult.NO_MATCH
            )
        await self._roles.grant(user.id, STUDENT, RoleScopeType.COHORT, signup.requested_cohort_id)
        return SignupMatchResult.MATCHED

    async def _match_mentor(
        self, user: User, signup: MemberSignup, phone_number: str
    ) -> SignupMatchResult:
        match = await self._mentors.link_contracts(
            user_id=user.id,
            name=user.name,
            phone_number=phone_number,
            nickname=signup.nickname,
            display_name_preference=signup.display_name_preference or DisplayNamePreference.NAME,
        )
        return SignupMatchResult.MATCHED if match.contract_ids else SignupMatchResult.NO_MATCH

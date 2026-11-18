"""수강생·멘토 가입 승인 관리 (계획 P7, decisions A6·A30·A33).

운영진:
- 대기 목록: 수강생은 `user.approve` 담당 범위(신청 기수)의 것, 멘토는 `contract.manage`가 있으면
  전부 본다.
- 수강생 승인: 담당 범위 안의 미가입·원천 존재 명단 하나를 골라 연결한다(다른 기수 명단도
  가능, 수강 상태 무관). 신청 기수와 고른 명단의 기수 모두 `user.approve` 범위여야 한다.
  STUDENT 역할은 고른 명단의 기수 범위로 준다.
- 멘토 승인(`contract.manage`): 미연결 멘토 계약을 0건 이상 골라 연결하고 멘토 프로필을 만든다.
- 반려: 사유(300자) 필수. 회원도 REJECTED가 된다.
승인·반려는 감사 로그를 남기고, 커밋 후 알림 메일을 워커로 보낸다.

신청자(반려된 회원): 최근 신청 조회, 재신청(새 신청 + 자동 매칭 다시, REJECTED → PENDING).
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.contexts.access.application.permissions import PermissionScope, PermissionTarget
from app.contexts.access.domain.catalog import STUDENT
from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.audit.application.recorder import AuditRecorder
from app.contexts.educator.application.mentor_onboarding import MentorMatch
from app.contexts.educator.domain.enums import DisplayNamePreference
from app.contexts.identity.application.signup import (
    MailDispatcher,
    SignupCohorts,
    settle_auto_match,
)
from app.contexts.identity.application.signup_mails import approval_mail, rejection_mail
from app.contexts.identity.application.signup_matching import RoleGranter, SignupMatcher
from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.enums import (
    MemberSignupStatus,
    MemberSignupType,
    member_account_type,
)
from app.contexts.identity.domain.repositories import (
    MemberSignupRepository,
    PendingSignupFilter,
    SignupVisibility,
    UserRepository,
)
from app.contexts.identity.domain.signup import MemberSignup
from app.core.clock import Clock
from app.core.uow import UnitOfWork
from app.shared.errors import BusinessRuleViolation, NotFoundError, PermissionDeniedError

APPROVE = "user.approve"
CONTRACT_MANAGE = "contract.manage"


class PermissionGate(Protocol):
    """access `PermissionChecker`."""

    async def has(self, user_id: uuid.UUID, code: str, target: PermissionTarget) -> bool: ...
    async def scope_of(self, user_id: uuid.UUID, code: str) -> PermissionScope: ...


class StudentSelector(Protocol):
    """academy `StudentClaims`."""

    async def cohort_of_claimable(self, student_id: uuid.UUID) -> uuid.UUID: ...
    async def claim_selected(self, student_id: uuid.UUID, *, user_id: uuid.UUID) -> uuid.UUID: ...


class MentorApprover(Protocol):
    """educator `MentorOnboarding`."""

    async def approve(
        self,
        *,
        user_id: uuid.UUID,
        nickname: str | None,
        display_name_preference: DisplayNamePreference,
        contract_ids: list[uuid.UUID],
    ) -> MentorMatch: ...


@dataclass(frozen=True, slots=True)
class SignupView:
    signup: MemberSignup
    user: User


def _denied() -> PermissionDeniedError:
    return PermissionDeniedError("이 작업을 할 권한이 없습니다.", code="permission_denied")


class SignupReviewService:
    def __init__(
        self,
        *,
        users: UserRepository,
        signups: MemberSignupRepository,
        permissions: PermissionGate,
        students: StudentSelector,
        mentors: MentorApprover,
        roles: RoleGranter,
        dispatcher: MailDispatcher,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        sender_name: str,
        login_url: str,
    ) -> None:
        self._users = users
        self._signups = signups
        self._permissions = permissions
        self._students = students
        self._mentors = mentors
        self._roles = roles
        self._dispatcher = dispatcher
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._sender_name = sender_name
        self._login_url = login_url

    async def list_pending(
        self,
        actor_id: uuid.UUID,
        *,
        signup_type: MemberSignupType | None,
        cohort_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SignupView], int]:
        scope = await self._permissions.scope_of(actor_id, APPROVE)
        visibility = SignupVisibility(
            all_students=scope.is_global,
            student_cohort_ids=scope.cohort_ids,
            student_bootcamp_ids=scope.bootcamp_ids,
            mentors=await self._permissions.has(
                actor_id, CONTRACT_MANAGE, PermissionTarget.any_scope()
            ),
        )
        signups, total = await self._signups.list_pending(
            PendingSignupFilter(
                visibility=visibility, signup_type=signup_type, cohort_id=cohort_id
            ),
            limit=limit,
            offset=offset,
        )
        users = {u.id: u for u in await self._users.list_by_ids([s.user_id for s in signups])}
        return [SignupView(s, users[s.user_id]) for s in signups if s.user_id in users], total

    async def approve_student(
        self, user_id: uuid.UUID, *, student_id: uuid.UUID, actor_id: uuid.UUID
    ) -> SignupView:
        async with self._uow:
            user, signup = await self._pending(user_id, MemberSignupType.STUDENT)
            await self._require_student_scope(actor_id, signup)
            cohort_id = await self._students.cohort_of_claimable(student_id)
            await self._require_cohort(actor_id, cohort_id)
            await self._students.claim_selected(student_id, user_id=user.id)
            await self._roles.grant(user.id, STUDENT, RoleScopeType.COHORT, cohort_id)
            await self._approve(
                actor_id,
                user,
                signup,
                {"student_id": str(student_id), "cohort_id": str(cohort_id)},
            )
        return SignupView(signup, user)

    async def approve_mentor(
        self, user_id: uuid.UUID, *, contract_ids: list[uuid.UUID], actor_id: uuid.UUID
    ) -> SignupView:
        async with self._uow:
            user, signup = await self._pending(user_id, MemberSignupType.MENTOR)
            await self._require_contract_manage(actor_id)
            match = await self._mentors.approve(
                user_id=user.id,
                nickname=signup.nickname,
                display_name_preference=signup.display_name_preference
                or DisplayNamePreference.NAME,
                contract_ids=contract_ids,
            )
            await self._approve(
                actor_id,
                user,
                signup,
                {
                    "mentor_id": str(match.mentor_id),
                    "contract_ids": [str(c) for c in match.contract_ids],
                },
            )
        return SignupView(signup, user)

    async def reject(self, user_id: uuid.UUID, *, reason: str, actor_id: uuid.UUID) -> SignupView:
        async with self._uow:
            user, signup = await self._pending(user_id, None)
            if signup.signup_type is MemberSignupType.STUDENT:
                await self._require_student_scope(actor_id, signup)
            else:
                await self._require_contract_manage(actor_id)
            signup.reject(reason, now=self._clock.now())
            user.reject()
            await self._signups.save(signup)
            await self._users.save(user)
            await self._audit.record(
                actor_user_id=actor_id,
                action="identity.member_signup.reject",
                target_type="member_signup",
                target_id=signup.id,
                after={"reject_reason": signup.reject_reason},
            )
            message = rejection_mail(
                user,
                signup.reject_reason or "",
                sender_name=self._sender_name,
                login_url=self._login_url,
            )
            self._uow.on_commit(lambda: self._dispatcher.dispatch(message))
        return SignupView(signup, user)

    # ------------------------------------------------------------------ 내부
    async def _pending(
        self, user_id: uuid.UUID, signup_type: MemberSignupType | None
    ) -> tuple[User, MemberSignup]:
        signup = await self._signups.get_pending_by_user(user_id)
        user = await self._users.get(user_id)
        if signup is None or user is None:
            raise NotFoundError("승인 대기 중인 가입 신청이 없습니다.", code="signup_not_found")
        if (signup_type is not None and signup.signup_type is not signup_type) or (
            user.account_type is not member_account_type(signup.signup_type)
        ):
            raise BusinessRuleViolation(
                "신청 유형에 맞는 승인 방법이 아닙니다.", code="signup_type_mismatch"
            )
        return user, signup

    async def _require_student_scope(self, actor_id: uuid.UUID, signup: MemberSignup) -> None:
        if signup.requested_cohort_id is None:
            raise _denied()
        await self._require_cohort(actor_id, signup.requested_cohort_id)

    async def _require_cohort(self, actor_id: uuid.UUID, cohort_id: uuid.UUID) -> None:
        if not await self._permissions.has(actor_id, APPROVE, PermissionTarget.cohort(cohort_id)):
            raise _denied()

    async def _require_contract_manage(self, actor_id: uuid.UUID) -> None:
        if not await self._permissions.has(actor_id, CONTRACT_MANAGE, PermissionTarget.any_scope()):
            raise _denied()

    async def _approve(
        self, actor_id: uuid.UUID, user: User, signup: MemberSignup, detail: dict[str, object]
    ) -> None:
        now = self._clock.now()
        signup.approve(now=now)
        user.approve(now=now)
        await self._signups.save(signup)
        await self._users.save(user)
        await self._audit.record(
            actor_user_id=actor_id,
            action="identity.member_signup.approve",
            target_type="member_signup",
            target_id=signup.id,
            after=detail,
        )
        message = approval_mail(user, sender_name=self._sender_name, login_url=self._login_url)
        self._uow.on_commit(lambda: self._dispatcher.dispatch(message))


@dataclass(frozen=True, slots=True, kw_only=True)
class ResubmitForm:
    signup_type: MemberSignupType
    cohort_id: uuid.UUID | None = None
    nickname: str | None = None
    display_name_preference: DisplayNamePreference | None = None


class MemberSignupSelfService:
    """신청자 본인: 최근 신청 조회와 반려 후 재신청."""

    def __init__(
        self,
        *,
        users: UserRepository,
        signups: MemberSignupRepository,
        cohorts: SignupCohorts,
        matcher: SignupMatcher,
        dispatcher: MailDispatcher,
        audit: AuditRecorder,
        uow: UnitOfWork,
        clock: Clock,
        sender_name: str,
        login_url: str,
    ) -> None:
        self._users = users
        self._signups = signups
        self._cohorts = cohorts
        self._matcher = matcher
        self._dispatcher = dispatcher
        self._audit = audit
        self._uow = uow
        self._clock = clock
        self._sender_name = sender_name
        self._login_url = login_url

    async def latest(self, user_id: uuid.UUID) -> MemberSignup:
        signup = await self._signups.get_latest_by_user(user_id)
        if signup is None:
            raise NotFoundError("가입 신청이 없습니다.", code="signup_not_found")
        return signup

    async def resubmit(self, user_id: uuid.UUID, form: ResubmitForm) -> SignupView:
        if form.signup_type is MemberSignupType.STUDENT and (
            form.cohort_id is None or not await self._cohorts.is_signup_cohort(form.cohort_id)
        ):
            raise BusinessRuleViolation("가입할 수 있는 기수를 선택하세요.", code="invalid_cohort")
        async with self._uow:
            user = await self._users.get(user_id)
            latest = await self._signups.get_latest_by_user(user_id)
            if user is None or latest is None or latest.status is not MemberSignupStatus.REJECTED:
                raise BusinessRuleViolation(
                    "반려된 신청만 다시 신청할 수 있습니다.", code="signup_not_rejected"
                )
            user.resubmit()
            user.change_member_type(member_account_type(form.signup_type))
            await self._users.save(user)
            is_student = form.signup_type is MemberSignupType.STUDENT
            signup = MemberSignup(
                user_id=user.id,
                signup_type=form.signup_type,
                requested_cohort_id=form.cohort_id if is_student else None,
                nickname=None if is_student else form.nickname,
                display_name_preference=None if is_student else form.display_name_preference,
            )
            result = await settle_auto_match(
                matcher=self._matcher,
                user=user,
                signup=signup,
                users=self._users,
                uow=self._uow,
                dispatcher=self._dispatcher,
                clock=self._clock,
                sender_name=self._sender_name,
                login_url=self._login_url,
            )
            await self._signups.add(signup)
            await self._audit.record(
                actor_user_id=user.id,
                action="identity.member_signup.resubmit",
                target_type="member_signup",
                target_id=signup.id,
                after={
                    "signup_type": signup.signup_type.value,
                    "match_result": result.value,
                    "status": signup.status.value,
                },
            )
        return SignupView(signup, user)

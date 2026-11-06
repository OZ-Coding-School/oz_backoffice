"""회원 관리 유스케이스 (CLI·관리 기능용 공개 서비스)."""

from app.contexts.identity.domain.entities import User
from app.contexts.identity.domain.repositories import UserRepository
from app.core.clock import Clock
from app.shared.errors import BusinessRuleViolation


class UserAdministration:
    def __init__(self, users: UserRepository, clock: Clock) -> None:
        self._users = users
        self._clock = clock

    async def ensure_approved_staff(
        self, email: str, *, staff_domain: str, name: str | None = None
    ) -> tuple[User, bool]:
        """운영진 회원을 승인 상태로 맞춘다. 없으면 만든다. (회원, 새로 만들었는지)를 돌려준다.

        미리 만든 회원은 그 이메일로 처음 Google 로그인할 때 연결된다.
        호출하는 쪽이 UnitOfWork를 연다.
        """
        email = email.strip().lower()
        if not email.endswith(f"@{staff_domain.lower()}"):
            raise BusinessRuleViolation(
                f"{staff_domain} 이메일만 운영진으로 등록할 수 있습니다.", code="not_staff_email"
            )
        user = await self._users.get_by_email(email)
        created = user is None
        if user is None:
            user = User(email=email, name=name or email.split("@", 1)[0])
            await self._users.add(user)
        if user.deleted_at is not None or (user.is_approved and not user.is_active):
            raise BusinessRuleViolation("탈퇴했거나 정지된 계정입니다.", code="account_disabled")
        if not user.is_approved:
            user.approve(now=self._clock.now())
            await self._users.save(user)
        return user, created

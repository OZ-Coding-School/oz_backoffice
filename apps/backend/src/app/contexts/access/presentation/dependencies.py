"""인증·권한 의존성 (다른 컨텍스트 라우터가 쓰는 공개 의존성).

- get_current_user: `Authorization: Bearer <access>` → 로그인한 회원. 탈퇴·정지 계정은 401
- require_approved_user: 승인(APPROVED)된 회원만 통과. 승인 전이면 403 (plan §2.2 게이트)

회원 조회 서비스(UserQueries)는 composition root(app.main)가 app.state.user_queries에 연결한다.
다른 컨텍스트의 infrastructure를 import하지 않기 위해서다 (import-linter 계약).
P3에서 require_permission(...)을 여기에 추가한다.
"""

from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.application.tokens import read_access_token
from app.contexts.identity.domain.entities import User
from app.core.dependencies import get_jwt_service
from app.core.security import JWTService
from app.shared.errors import AuthenticationError, PermissionDeniedError

_bearer = HTTPBearer(auto_error=False, description="access 토큰")


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
    users: Annotated[UserQueries, Depends(get_user_queries)],
) -> User:
    if credentials is None:
        raise AuthenticationError("로그인이 필요합니다.", code="unauthenticated")
    user_id = read_access_token(jwt, credentials.credentials)
    return await users.get_authenticated(user_id)


async def require_approved_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_approved:
        raise PermissionDeniedError("승인 후 이용할 수 있습니다.", code="approval_required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
ApprovedUser = Annotated[User, Depends(require_approved_user)]

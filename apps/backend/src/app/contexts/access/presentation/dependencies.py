"""인증·권한 의존성 (다른 컨텍스트 라우터가 쓰는 공개 의존성).

- get_current_user: `Authorization: Bearer <access>` → 로그인한 회원. 탈퇴·정지 계정은 401
- require_approved_user: 승인(APPROVED)된 회원만 통과. 승인 전이면 403 (plan §2.2 게이트)

회원 조회 서비스(UserQueries)는 composition root(app.main)가 app.state.user_queries에 연결한다.
다른 컨텍스트의 infrastructure를 import하지 않기 위해서다 (import-linter 계약).
권한 출처(StaffGrantSource: 최고 관리자 필드 + 직위 권한·데이터 범위 + 담당 배정, A87)는
app.state.grant_source에 연결한다.
- require_permission(code, ...): 승인된 회원 + 권한 코드 + 범위(경로의 과정·기수 ID) 검사

"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.contexts.access.application.permissions import (
    CohortDirectory,
    GrantSource,
    PermissionChecker,
    PermissionTarget,
    ensure_known_permission,
)
from app.contexts.identity.application.auth_service import UserQueries
from app.contexts.identity.application.tokens import read_access_token
from app.contexts.identity.domain.entities import User
from app.core.dependencies import get_jwt_service
from app.core.security import JWTService
from app.shared.errors import AuthenticationError, NotFoundError, PermissionDeniedError

_bearer = HTTPBearer(auto_error=False, description="access 토큰")


def get_user_queries(request: Request) -> UserQueries:
    return cast("UserQueries", request.app.state.user_queries)


def get_grant_source(request: Request) -> GrantSource:
    return cast("GrantSource", request.app.state.grant_source)


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


async def require_super_admin(user: Annotated[User, Depends(require_approved_user)]) -> User:
    """최고 관리자만 (회원 필드, A87)."""
    if not user.is_super_admin:
        raise PermissionDeniedError("최고 관리자만 할 수 있습니다.", code="super_admin_only")
    return user


SuperAdmin = Annotated[User, Depends(require_super_admin)]


def get_cohort_directory(request: Request) -> CohortDirectory:
    return cast("CohortDirectory", request.app.state.academy_catalog)


def get_permission_checker(
    grants: Annotated[GrantSource, Depends(get_grant_source)],
    cohorts: Annotated[CohortDirectory, Depends(get_cohort_directory)],
) -> PermissionChecker:
    """요청 단위로 하나 만든다(FastAPI 의존성 캐시). 권한은 요청당 한 번만 읽는다."""
    return PermissionChecker(grants, cohorts)


PermissionCheckerDep = Annotated[PermissionChecker, Depends(get_permission_checker)]


def _path_uuid(request: Request, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(request.path_params[name]))
    except (KeyError, ValueError) as exc:
        raise NotFoundError("대상을 찾을 수 없습니다.", code="not_found") from exc


def require_permission(
    code: str,
    *,
    cohort_param: str | None = None,
    bootcamp_param: str | None = None,
    any_scope: bool = False,
) -> Callable[..., Awaitable[User]]:
    """권한 의존성을 만든다. 승인된 회원이어야 하고, 범위는 아래 중 하나로 정한다.

    - 기본: 전체(GLOBAL) 범위 권한이 필요하다.
    - cohort_param / bootcamp_param: 경로 파라미터의 기수·과정에 대한 권한이 필요하다.
      BOOTCAMP 범위 역할은 그 과정의 모든 기수에 적용된다.
    - any_scope=True: 어느 범위든 그 권한이 있는 역할이 하나라도 있으면 된다.

        @router.post("/cohorts/{cohort_id}/teams")
        async def create_team(
            user: Annotated[User, Depends(require_permission("mentoring.team.manage",
                                                              cohort_param="cohort_id"))],
        ) -> ...
    """
    ensure_known_permission(code)
    if sum((cohort_param is not None, bootcamp_param is not None, any_scope)) > 1:
        raise ValueError("범위는 cohort_param, bootcamp_param, any_scope 중 하나만 지정한다.")

    async def dependency(
        request: Request, user: ApprovedUser, checker: PermissionCheckerDep
    ) -> User:
        if cohort_param is not None:
            target = PermissionTarget.cohort(_path_uuid(request, cohort_param))
        elif bootcamp_param is not None:
            target = PermissionTarget.bootcamp(_path_uuid(request, bootcamp_param))
        elif any_scope:
            target = PermissionTarget.any_scope()
        else:
            target = PermissionTarget.global_()
        await checker.require(user.id, code, target)
        return user

    return dependency

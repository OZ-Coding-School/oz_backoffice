"""identity 요청·응답 스키마."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.contexts.access.domain.enums import RoleScopeType
from app.contexts.identity.domain.enums import UserApprovalStatus


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - 토큰 유형 이름이다
    expires_at: datetime


class RoleGrantResponse(BaseModel):
    role: str
    scope_type: RoleScopeType
    scope_id: uuid.UUID | None
    expires_at: datetime | None


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    phone_number: str | None
    approval_status: UserApprovalStatus
    approved_at: datetime | None
    roles: list[RoleGrantResponse]

"""identity 요청·응답 스키마."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.contexts.identity.domain.enums import AccountType, UserApprovalStatus


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - 토큰 유형 이름이다
    expires_at: datetime


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    account_type: AccountType = Field(
        description="STUDENT: 수강생, MENTOR: 멘토, STAFF: 운영진 (A61·A65)"
    )
    phone_number: str | None
    approval_status: UserApprovalStatus
    approved_at: datetime | None
    is_super_admin: bool = Field(description="최고 관리자 (모든 권한, A87)")

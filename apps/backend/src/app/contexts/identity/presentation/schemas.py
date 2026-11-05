"""identity 요청·응답 스키마."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.contexts.identity.domain.enums import UserApprovalStatus


class AuthorizationUrlResponse(BaseModel):
    authorization_url: str


class GoogleCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=256)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - 토큰 유형 이름이다
    expires_at: datetime


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    phone_number: str | None
    approval_status: UserApprovalStatus
    approved_at: datetime | None

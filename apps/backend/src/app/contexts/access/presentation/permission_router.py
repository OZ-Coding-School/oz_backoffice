"""권한 정의 API (GET /admin/permissions, decisions A86·A87). 권한: access.role.read.

직위별 권한 화면이 권한 표(영역·엔터티·동작)를 그릴 때 쓴다. 직위의 권한 묶음은 organization의
`/admin/positions` API가 다룬다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.contexts.access.domain.catalog import PERMISSION_DEFINITIONS
from app.contexts.access.presentation.dependencies import require_permission
from app.contexts.identity.domain.entities import User

router = APIRouter(prefix="/admin/permissions", tags=["admin-permissions"])


class PermissionDefinitionResponse(BaseModel):
    code: str
    area: str = Field(description="화면 묶음: 조직·학사·회원 관리·강사·멘토·멘토링")
    entity: str = Field(description="엔터티 이름 (같은 엔터티의 권한은 한 행)")
    action: str = Field(description="동작: 조회·관리·동기화·취소·마감")
    description: str
    cohort_bound: bool = Field(description="기수에 속한 엔터티 — 직위의 데이터 범위가 적용된다")
    requires: str | None = Field(description="함께 켜야 하는 조회 권한 (A86)")


Reader = Annotated[User, Depends(require_permission("access.role.read"))]


@router.get("", response_model=list[PermissionDefinitionResponse])
async def list_permissions(_: Reader) -> list[PermissionDefinitionResponse]:
    """권한 정의 (정의 순서)."""
    return [
        PermissionDefinitionResponse(
            code=p.code,
            area=p.area,
            entity=p.entity,
            action=p.action,
            description=p.description,
            cohort_bound=p.cohort_bound,
            requires=p.requires,
        )
        for p in PERMISSION_DEFINITIONS
    ]

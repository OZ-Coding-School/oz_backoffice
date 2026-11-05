"""/api/v1 라우터 통합. 컨텍스트별 presentation 라우터를 여기서 include한다."""

from fastapi import APIRouter

from app.contexts.identity.presentation.router import auth_router, me_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(me_router)

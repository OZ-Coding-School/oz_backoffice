"""/api/v1 라우터 통합. 컨텍스트별 presentation 라우터를 여기서 include한다."""

from fastapi import APIRouter

router = APIRouter()

# 예) from app.contexts.mentoring.presentation.routers import router as mentoring_router
#     router.include_router(mentoring_router, prefix="/mentoring")

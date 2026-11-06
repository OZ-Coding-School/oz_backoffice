"""/api/v1 라우터 통합. 컨텍스트별 presentation 라우터를 여기서 include한다."""

from fastapi import APIRouter

from app.contexts.access.presentation.admin_router import router as user_roles_router
from app.contexts.identity.presentation.router import auth_router, me_router
from app.contexts.organization.presentation.admin_router import (
    router as staff_registration_admin_router,
)
from app.contexts.organization.presentation.router import router as staff_registration_router
from app.contexts.organization.presentation.staff_router import router as staff_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(staff_registration_router)
router.include_router(staff_registration_admin_router)
router.include_router(staff_router)
router.include_router(user_roles_router)

"""/api/v1 라우터 통합. 컨텍스트별 presentation 라우터를 여기서 include한다."""

from fastapi import APIRouter

from app.contexts.academy.presentation.admin_router import router as academy_router
from app.contexts.academy.presentation.roster_router import router as roster_router
from app.contexts.access.presentation.admin_router import router as user_roles_router
from app.contexts.educator.presentation.admin_router import router as contract_router
from app.contexts.educator.presentation.mentor_router import admin_router as mentor_admin_router
from app.contexts.educator.presentation.mentor_router import me_router as mentor_me_router
from app.contexts.identity.presentation.approval_router import admin_router as approval_admin_router
from app.contexts.identity.presentation.approval_router import me_router as member_signup_router
from app.contexts.identity.presentation.password_router import router as password_router
from app.contexts.identity.presentation.router import auth_router, me_router
from app.contexts.identity.presentation.signup_router import router as signup_router
from app.contexts.mentoring.presentation.assignment_router import (
    admin_router as mentor_assignment_admin_router,
)
from app.contexts.mentoring.presentation.assignment_router import (
    me_router as mentor_assignment_me_router,
)
from app.contexts.mentoring.presentation.availability_router import (
    router as mentor_available_times_router,
)
from app.contexts.mentoring.presentation.balance_router import (
    admin_router as balance_admin_router,
)
from app.contexts.mentoring.presentation.balance_router import me_router as balance_me_router
from app.contexts.mentoring.presentation.request_router import (
    admin_router as request_admin_router,
)
from app.contexts.mentoring.presentation.request_router import me_router as request_me_router
from app.contexts.mentoring.presentation.request_router import router as request_router
from app.contexts.mentoring.presentation.schedule_router import (
    admin_router as mentor_schedule_admin_router,
)
from app.contexts.mentoring.presentation.schedule_router import (
    me_router as mentor_schedule_me_router,
)
from app.contexts.mentoring.presentation.session_router import (
    admin_router as session_admin_router,
)
from app.contexts.mentoring.presentation.session_router import me_router as session_me_router
from app.contexts.mentoring.presentation.session_router import router as session_router
from app.contexts.mentoring.presentation.settings_router import router as mentoring_settings_router
from app.contexts.mentoring.presentation.team_router import admin_router as team_admin_router
from app.contexts.mentoring.presentation.team_router import me_router as team_me_router
from app.contexts.organization.presentation.admin_router import (
    router as staff_registration_admin_router,
)
from app.contexts.organization.presentation.org_router import router as organization_router
from app.contexts.organization.presentation.router import router as staff_registration_router
from app.contexts.organization.presentation.staff_router import router as staff_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(signup_router)
router.include_router(password_router)
router.include_router(member_signup_router)
router.include_router(approval_admin_router)
router.include_router(me_router)
router.include_router(staff_registration_router)
router.include_router(staff_registration_admin_router)
router.include_router(staff_router)
router.include_router(user_roles_router)
router.include_router(organization_router)
router.include_router(academy_router)
router.include_router(roster_router)
router.include_router(contract_router)
router.include_router(mentor_me_router)
router.include_router(mentor_admin_router)
router.include_router(mentoring_settings_router)
router.include_router(mentor_assignment_admin_router)
router.include_router(mentor_assignment_me_router)
router.include_router(mentor_schedule_me_router)
router.include_router(mentor_schedule_admin_router)
router.include_router(mentor_available_times_router)
router.include_router(team_admin_router)
router.include_router(team_me_router)
router.include_router(balance_admin_router)
router.include_router(balance_me_router)
router.include_router(request_router)
router.include_router(request_me_router)
router.include_router(request_admin_router)
router.include_router(session_router)
router.include_router(session_me_router)
router.include_router(session_admin_router)

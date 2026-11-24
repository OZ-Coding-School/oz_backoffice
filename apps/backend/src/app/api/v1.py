"""/api/v1 라우터 통합. 컨텍스트별 presentation 라우터를 여기서 include한다."""

from fastapi import APIRouter

from app.contexts.academy.presentation.admin_router import router as academy_router
from app.contexts.academy.presentation.me_router import router as my_enrollments_router
from app.contexts.academy.presentation.roster_router import router as roster_router
from app.contexts.access.presentation.admin_router import router as user_roles_router
from app.contexts.access.presentation.holder_router import router as role_holders_router
from app.contexts.access.presentation.me_router import router as staff_access_router
from app.contexts.access.presentation.role_router import router as role_catalog_router
from app.contexts.educator.presentation.admin_router import router as contract_router
from app.contexts.educator.presentation.mentor_router import admin_router as mentor_admin_router
from app.contexts.educator.presentation.mentor_router import me_router as mentor_me_router
from app.contexts.identity.presentation.approval_router import admin_router as approval_admin_router
from app.contexts.identity.presentation.approval_router import me_router as member_signup_router
from app.contexts.identity.presentation.password_change_router import (
    me_router as password_change_me_router,
)
from app.contexts.identity.presentation.password_change_router import (
    verify_router as password_change_verify_router,
)
from app.contexts.identity.presentation.password_router import router as password_router
from app.contexts.identity.presentation.router import auth_router, me_router
from app.contexts.identity.presentation.signup_router import router as signup_router
from app.contexts.mentoring.presentation.artifact_router import (
    admin_router as artifact_admin_router,
)
from app.contexts.mentoring.presentation.artifact_router import (
    link_router as artifact_link_router,
)
from app.contexts.mentoring.presentation.artifact_router import router as artifact_router
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
from app.contexts.mentoring.presentation.chat_router import admin_router as chat_admin_router
from app.contexts.mentoring.presentation.chat_router import me_router as chat_me_router
from app.contexts.mentoring.presentation.chat_router import router as chat_router
from app.contexts.mentoring.presentation.mentee_router import admin_router as mentee_admin_router
from app.contexts.mentoring.presentation.record_router import (
    admin_router as record_admin_router,
)
from app.contexts.mentoring.presentation.record_router import router as record_router
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
from app.contexts.mentoring.presentation.settlement_router import (
    admin_router as settlement_admin_router,
)
from app.contexts.mentoring.presentation.settlement_router import (
    me_router as settlement_me_router,
)
from app.contexts.mentoring.presentation.student_router import router as student_mentoring_router
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
router.include_router(password_change_verify_router)
router.include_router(password_change_me_router)
router.include_router(member_signup_router)
router.include_router(approval_admin_router)
router.include_router(me_router)
router.include_router(staff_registration_router)
router.include_router(staff_registration_admin_router)
router.include_router(staff_router)
router.include_router(user_roles_router)
router.include_router(role_catalog_router)
router.include_router(role_holders_router)
router.include_router(staff_access_router)
router.include_router(organization_router)
router.include_router(academy_router)
router.include_router(roster_router)
router.include_router(my_enrollments_router)
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
router.include_router(student_mentoring_router)
router.include_router(balance_admin_router)
router.include_router(balance_me_router)
router.include_router(request_router)
router.include_router(request_me_router)
router.include_router(request_admin_router)
router.include_router(artifact_router)
router.include_router(artifact_link_router)
router.include_router(artifact_admin_router)
router.include_router(record_router)  # 세션 라우터의 /{session_id}보다 먼저
router.include_router(record_admin_router)
router.include_router(session_router)
router.include_router(settlement_admin_router)
router.include_router(settlement_me_router)
router.include_router(session_me_router)
router.include_router(session_admin_router)
router.include_router(mentee_admin_router)
router.include_router(chat_router)
router.include_router(chat_me_router)
router.include_router(chat_admin_router)

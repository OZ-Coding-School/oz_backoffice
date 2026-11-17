"""역할·권한 정의 (plan §2.3 권한표, decisions M31). 시드의 단일 출처다.

역할은 계층이 아니라 권한 집합이다. 멘토·수강생 기능은 권한 코드가 아니라 소유 관계로 검사하므로
MENTOR·STUDENT 역할에는 권한 코드가 없다.
"""

from dataclasses import dataclass

from app.contexts.access.domain.enums import RoleScopeType

PERMISSIONS: dict[str, str] = {
    "org.manage": "부서·직위·직원·과정·HRD·기수 관리",
    "role.assign": "역할 직접 부여, 운영진 가입 승인",
    "staff.assign": "과정·기수 담당자 배정",
    "user.approve": "가입 승인·반려, 수동 매칭 (매니저·조교는 담당 범위의 수강생만)",
    "roster.sync": "명단 동기화 실행·명단·이력 조회 (매니저·조교는 담당 범위만)",
    "contract.manage": "계약·계약서, 멘토/강사 연결",
    "mentor.manage": "멘토 목록·프로필 대리 수정·활성화",
    "mentoring.settings.manage": "기수 멘토링 설정, 금지 시간대",
    "mentoring.assignment.manage": "멘토 배정·단가",
    "mentoring.team.manage": "멘토링 팀 구성",
    "mentoring.balance.grant": "멘토링 크레딧 지급·조정",
    "mentoring.request.read": "멘토링 신청·세션 조회",
    "mentoring.request.cancel": "운영진 취소, 환불 선택",
    "mentoring.settlement.close": "정산 집계·마감·조회",
}

_ASSISTANT = frozenset(
    {
        "user.approve",
        "roster.sync",
        "mentoring.team.manage",
        "mentoring.balance.grant",
        "mentoring.request.read",
        "mentoring.request.cancel",
    }
)
_MANAGER = _ASSISTANT | {
    "contract.manage",
    "mentor.manage",
    "mentoring.settings.manage",
    "mentoring.assignment.manage",
    "mentoring.settlement.close",
}
_TEAM_LEAD = _MANAGER | {"staff.assign"}

SUPER_ADMIN = "SUPER_ADMIN"
TEAM_LEAD = "TEAM_LEAD"
COHORT_MANAGER = "COHORT_MANAGER"
COHORT_ASSISTANT = "COHORT_ASSISTANT"
MENTOR = "MENTOR"
STUDENT = "STUDENT"


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    code: str
    name: str
    description: str
    permissions: frozenset[str]
    scopes: frozenset[RoleScopeType]


_STAFF_SCOPES = frozenset({RoleScopeType.BOOTCAMP, RoleScopeType.COHORT})

ROLES: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        SUPER_ADMIN,
        "최고 관리자",
        "모든 권한 (전체 범위)",
        frozenset(PERMISSIONS),
        frozenset({RoleScopeType.GLOBAL}),
    ),
    RoleDefinition(
        TEAM_LEAD,
        "팀리드",
        "매니저 권한 + 멘토 관리·담당자 배정 (전체 범위, decisions A36)",
        _TEAM_LEAD,
        frozenset({RoleScopeType.GLOBAL}),
    ),
    RoleDefinition(COHORT_MANAGER, "운영 매니저", "담당 과정·기수의 운영", _MANAGER, _STAFF_SCOPES),
    RoleDefinition(
        COHORT_ASSISTANT, "조교", "담당 과정·기수의 운영 보조", _ASSISTANT, _STAFF_SCOPES
    ),
    RoleDefinition(
        MENTOR, "멘토", "배정된 기수의 멘토링 (소유 관계로 검사)", frozenset(), _STAFF_SCOPES
    ),
    RoleDefinition(
        STUDENT,
        "수강생",
        "수강 중인 기수의 멘토링 (소유 관계로 검사)",
        frozenset(),
        frozenset({RoleScopeType.COHORT}),
    ),
)

ROLES_BY_CODE = {role.code: role for role in ROLES}

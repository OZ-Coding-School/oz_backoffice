"""역할·권한 정의 (plan §2.3 권한표, decisions M31·A84·A86).

권한은 엔터티 × 조회/관리(와 몇 가지 특별한 동작)다(A86).

권한 코드 목록과 기본 역할은 코드가 정한다. 기본 역할의 권한 묶음은 **초기값**이고,
역할을 처음 만들 때만 DB에 넣는다. 이후 역할별 권한은 DB `role_permissions`가 출처다(A84).
최고 관리자는 항상 모든 권한이다.

역할은 계층이 아니라 권한 집합이다. 멘토·수강생 기능은 권한 코드가 아니라 소유 관계로 검사하므로
MENTOR·STUDENT 역할에는 권한 코드가 없다.
"""

from dataclasses import dataclass

from app.contexts.access.domain.enums import RoleScopeType


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """권한 하나 (A86). 엔터티마다 조회(read)·관리(manage) 또는 업무상 특별한 동작."""

    code: str
    area: str  # 화면 묶음 (조직·학사·회원·권한·강사·멘토·멘토링)
    entity: str  # 엔터티 이름
    action: str  # 동작 이름 (조회·관리·동기화·취소·마감)
    description: str
    global_only: bool = False  # 전체 범위 역할에만 줄 수 있음
    requires: str | None = None  # 함께 있어야 하는 조회 권한 (관리는 조회를 포함)


def _entity(
    prefix: str, area: str, entity: str, read: str, manage: str, *, global_only: bool = False
) -> list[PermissionDefinition]:
    return [
        PermissionDefinition(f"{prefix}.read", area, entity, "조회", read, global_only),
        PermissionDefinition(
            f"{prefix}.manage", area, entity, "관리", manage, global_only, f"{prefix}.read"
        ),
    ]


PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    *_entity(
        "org.department",
        "조직",
        "부서·팀",
        "부서·팀 조회",
        "부서·팀 추가·수정·삭제, 과정 담당 팀 지정",
        global_only=True,
    ),
    *_entity("org.position", "조직", "직위", "직위 조회", "직위 추가·수정·삭제", global_only=True),
    *_entity(
        "org.employee", "조직", "직원", "직원 목록·상세 조회", "직원 소속 수정", global_only=True
    ),
    *_entity(
        "academy.hrd",
        "학사",
        "HRD 과정·회차",
        "HRD 과정·회차 조회",
        "HRD 과정·회차 수정·삭제",
        global_only=True,
    ),
    *_entity(
        "academy.bootcamp", "학사", "과정", "과정 조회", "과정 추가·수정·삭제", global_only=True
    ),
    *_entity("academy.cohort", "학사", "기수", "기수 조회", "기수 수정·삭제"),
    PermissionDefinition(
        "academy.roster.read", "학사", "수강생 명단", "조회", "명단·동기화 이력 조회"
    ),
    PermissionDefinition(
        "academy.roster.sync",
        "학사",
        "수강생 명단",
        "동기화",
        "명단 동기화 실행",
        requires="academy.roster.read",
    ),
    *_entity(
        "member.approval",
        "회원·권한",
        "회원 가입 승인",
        "가입 신청 조회",
        "가입 승인·반려, 수동 매칭",
    ),
    *_entity(
        "staff.registration",
        "회원·권한",
        "운영진 가입 승인",
        "운영진 신청 조회",
        "운영진 승인·반려",
        global_only=True,
    ),
    *_entity(
        "staff.assignment",
        "회원·권한",
        "담당자",
        "과정·기수 담당자 조회",
        "담당자 배정·해제",
        global_only=True,
    ),
    *_entity(
        "access.role",
        "회원·권한",
        "역할·권한",
        "역할·권한·보유자 조회",
        "역할 추가·수정·삭제, 권한 변경, 역할 부여·회수",
        global_only=True,
    ),
    *_entity(
        "educator.contract",
        "강사·멘토",
        "계약",
        "계약·계약서 조회",
        "계약 등록·확정·해지, 회원 연결",
    ),
    *_entity(
        "educator.mentor",
        "강사·멘토",
        "멘토",
        "멘토 목록·프로필·일정 조회",
        "프로필 대리 수정, 활성화·비활성화, 일정 대리",
    ),
    *_entity(
        "mentoring.settings",
        "멘토링",
        "멘토링 설정",
        "기수 설정·금지 시간대·추가 휴일 조회",
        "설정·금지 시간대·추가 휴일 변경",
    ),
    *_entity("mentoring.assignment", "멘토링", "멘토 배정", "배정·단가 조회", "배정·단가 변경"),
    *_entity("mentoring.team", "멘토링", "멘토링 팀", "팀 조회", "팀 구성·팀원 변경"),
    *_entity(
        "mentoring.balance",
        "멘토링",
        "시간 계좌",
        "계좌·원장 조회",
        "시간 지급·조정, 유효 기간 변경",
    ),
    PermissionDefinition(
        "mentoring.request.read", "멘토링", "신청·세션", "조회", "신청·세션·멘티 조회"
    ),
    PermissionDefinition(
        "mentoring.request.cancel",
        "멘토링",
        "신청·세션",
        "취소",
        "운영진 취소, 환불 선택",
        requires="mentoring.request.read",
    ),
    PermissionDefinition(
        "mentoring.record.read",
        "멘토링",
        "기록·녹화",
        "조회",
        "세션 기록·내부 메모·녹화·미제출 조회",
    ),
    PermissionDefinition("mentoring.chat.read", "멘토링", "채팅", "조회", "채팅방·메시지 열람"),
    PermissionDefinition(
        "mentoring.settlement.read", "멘토링", "정산", "조회", "정산 목록·상세·CSV"
    ),
    PermissionDefinition(
        "mentoring.settlement.close",
        "멘토링",
        "정산",
        "마감",
        "정산 집계·마감",
        requires="mentoring.settlement.read",
    ),
)

PERMISSIONS_BY_CODE = {p.code: p for p in PERMISSION_DEFINITIONS}
PERMISSIONS: dict[str, str] = {p.code: p.description for p in PERMISSION_DEFINITIONS}
GLOBAL_ONLY_PERMISSIONS = frozenset(p.code for p in PERMISSION_DEFINITIONS if p.global_only)


def _all(*prefixes: str) -> frozenset[str]:
    return frozenset(c for c in PERMISSIONS if c.rsplit(".", 1)[0] in prefixes)


# 예전 기능 묶음 권한(A84 이전) → 새 권한. `seed-roles`가 저장된 역할 매핑을 바꿀 때 쓴다 (A86)
LEGACY_PERMISSIONS: dict[str, frozenset[str]] = {
    "org.manage": _all(
        "org.department",
        "org.position",
        "org.employee",
        "academy.hrd",
        "academy.bootcamp",
        "academy.cohort",
    ),
    "role.assign": _all("staff.registration", "access.role"),
    "staff.assign": _all("staff.assignment") | {"org.employee.read"},
    "user.approve": _all("member.approval"),
    "roster.sync": _all("academy.roster"),
    "contract.manage": _all("educator.contract"),
    "mentor.manage": _all("educator.mentor"),
    "mentoring.settings.manage": _all("mentoring.settings"),
    "mentoring.assignment.manage": _all("mentoring.assignment"),
    "mentoring.team.manage": _all("mentoring.team"),
    "mentoring.balance.grant": _all("mentoring.balance"),
    "mentoring.request.read": frozenset(
        {"mentoring.request.read", "mentoring.record.read", "mentoring.chat.read"}
    ),
    "mentoring.request.cancel": frozenset({"mentoring.request.read", "mentoring.request.cancel"}),
    "mentoring.settlement.close": _all("mentoring.settlement"),
}

_ASSISTANT = _all(
    "member.approval",
    "academy.roster",
    "mentoring.team",
    "mentoring.balance",
    "mentoring.request",
    "mentoring.record",
    "mentoring.chat",
)
_MANAGER = _ASSISTANT | _all(
    "educator.contract",
    "educator.mentor",
    "mentoring.settings",
    "mentoring.assignment",
    "mentoring.settlement",
)
_TEAM_LEAD = _MANAGER | _all("staff.assignment") | {"org.employee.read"}

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
BUILTIN_ROLE_CODES = frozenset(ROLES_BY_CODE)
# 권한 코드가 없고 소유 관계로 검사하는 역할 — 역할·권한 관리 화면에 나오지 않는다
HIDDEN_ROLE_CODES = frozenset({MENTOR, STUDENT})

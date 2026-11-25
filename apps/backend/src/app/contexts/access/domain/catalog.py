"""권한 정의 (decisions A86·A87).

권한은 엔터티 × 조회/관리(와 몇 가지 특별한 동작)다(A86). 권한 묶음은 직위에 붙고(직위 = 역할, A87),
최고 관리자(회원 필드)는 모든 권한이다. 데이터 범위는 직위의 데이터 범위와 담당 배정이 정하며,
기수에 속한 엔터티(`cohort_bound`)에만 적용한다.
"""

# ruff: noqa: E501  (권한 표는 한 줄에 하나씩 읽기 쉽게 둔다)

from collections.abc import Iterable
from dataclasses import dataclass

from app.shared.errors import BusinessRuleViolation


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """권한 하나 (A86). 엔터티마다 조회(read)·관리(manage) 또는 업무상 특별한 동작."""

    code: str
    area: str  # 화면 묶음 (조직·학사·회원·권한·강사·멘토·멘토링)
    entity: str  # 엔터티 이름
    action: str  # 동작 이름 (조회·관리·동기화·취소·마감)
    description: str
    cohort_bound: bool = False  # 기수에 속한 엔터티: 데이터 범위(담당 과정·기수)가 적용된다
    requires: str | None = None  # 함께 있어야 하는 조회 권한 (관리는 조회를 포함)


def _entity(
    prefix: str, area: str, entity: str, read: str, manage: str, *, cohort_bound: bool = False
) -> list[PermissionDefinition]:
    return [
        PermissionDefinition(f"{prefix}.read", area, entity, "조회", read, cohort_bound),
        PermissionDefinition(
            f"{prefix}.manage", area, entity, "관리", manage, cohort_bound, f"{prefix}.read"
        ),
    ]


def _action(
    code: str, entity: str, action: str, description: str, requires: str | None = None
) -> PermissionDefinition:
    """멘토링·학사의 조회 전용·특별 동작 (모두 기수에 속한 엔터티)."""
    area = "학사" if code.startswith("academy.") else "멘토링"
    return PermissionDefinition(code, area, entity, action, description, True, requires)


# fmt: off
PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    *_entity("org.department", "조직", "부서·팀", "부서·팀 조회", "부서·팀 추가·수정·삭제, 과정 담당 팀 지정"),
    *_entity("org.position", "조직", "직위", "직위 조회", "직위 추가·수정·삭제"),
    *_entity("org.employee", "조직", "직원", "직원 목록·상세 조회", "직원 소속·직위 수정"),
    *_entity("staff.assignment", "조직", "담당자", "과정·기수 담당자 조회", "담당자 배정·해제"),
    *_entity("access.role", "조직", "직위별 권한", "직위별 권한 조회", "직위별 권한 변경"),
    *_entity("academy.hrd", "학사", "HRD 과정·회차", "HRD 과정·회차 조회", "HRD 과정·회차 수정·삭제"),
    *_entity("academy.bootcamp", "학사", "과정", "과정 조회", "과정 추가·수정·삭제"),
    *_entity("academy.cohort", "학사", "기수", "기수 조회", "기수 수정·삭제", cohort_bound=True),
    _action("academy.roster.read", "수강생 명단", "조회", "명단·동기화 이력 조회"),
    _action("academy.roster.sync", "수강생 명단", "동기화", "명단 동기화 실행", "academy.roster.read"),
    *_entity("member.approval", "회원 관리", "회원 가입 승인", "가입 신청 조회", "가입 승인·반려, 수동 매칭", cohort_bound=True),
    *_entity("staff.registration", "회원 관리", "운영진 가입 승인", "운영진 신청 조회", "운영진 승인·반려"),
    *_entity("member.user", "회원 관리", "회원", "전체 회원 목록·상세 조회", "계정 비활성화·활성화"),
    *_entity("educator.contract", "강사·멘토", "계약", "계약·계약서 조회", "계약 등록·확정·해지, 회원 연결"),
    *_entity("educator.mentor", "강사·멘토", "멘토", "멘토 목록·프로필·일정 조회", "프로필 대리 수정, 활성화·비활성화, 일정 대리"),
    *_entity("mentoring.settings", "멘토링", "멘토링 설정", "기수 설정·금지 시간대·추가 휴일 조회", "설정·금지 시간대·추가 휴일 변경", cohort_bound=True),
    *_entity("mentoring.assignment", "멘토링", "멘토 배정", "배정·단가 조회", "배정·단가 변경", cohort_bound=True),
    *_entity("mentoring.team", "멘토링", "멘토링 팀", "팀 조회", "팀 구성·팀원 변경", cohort_bound=True),
    *_entity("mentoring.balance", "멘토링", "시간 계좌", "계좌·원장 조회", "시간 지급·조정, 유효 기간 변경", cohort_bound=True),
    _action("mentoring.request.read", "신청·세션", "조회", "신청·세션·멘티 조회"),
    _action("mentoring.request.cancel", "신청·세션", "취소", "운영진 취소, 환불 선택", "mentoring.request.read"),
    _action("mentoring.record.read", "기록·녹화", "조회", "세션 기록·내부 메모·녹화·미제출 조회"),
    _action("mentoring.chat.read", "채팅", "조회", "채팅방·메시지 열람"),
    _action("mentoring.settlement.read", "정산", "조회", "정산 목록·상세·CSV"),
    _action("mentoring.settlement.close", "정산", "마감", "정산 집계·마감", "mentoring.settlement.read"),
)
# fmt: on

PERMISSIONS_BY_CODE = {p.code: p for p in PERMISSION_DEFINITIONS}
PERMISSIONS: dict[str, str] = {p.code: p.description for p in PERMISSION_DEFINITIONS}


def _all(*prefixes: str) -> frozenset[str]:
    return frozenset(c for c in PERMISSIONS if c.rsplit(".", 1)[0] in prefixes)


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

# 개발 시드(`seed-dev-org`)가 직위에 넣는 권한 묶음. 운영에서는 화면에서 정한다 (A87)
DEV_POSITION_PERMISSIONS: dict[str, frozenset[str]] = {
    "팀리드": _TEAM_LEAD,
    "운영 매니저": _MANAGER,
    "러닝 코치": _MANAGER,
    "조교": _ASSISTANT,
}


def validate_permissions(codes: Iterable[str]) -> frozenset[str]:
    """직위 권한 묶음 검사: 정의된 코드만, 관리·동기화·취소·마감은 조회와 함께 (A86)."""
    wanted = frozenset(codes)
    unknown = sorted(wanted - PERMISSIONS.keys())
    if unknown:
        raise BusinessRuleViolation(
            f"정의되지 않은 권한입니다: {', '.join(unknown)}", code="permission_not_found"
        )
    missing_read = sorted(
        code
        for code in wanted
        if (needed := PERMISSIONS_BY_CODE[code].requires) and needed not in wanted
    )
    if missing_read:
        raise BusinessRuleViolation(
            "관리·동기화·취소·마감 권한은 조회 권한과 함께 줘야 합니다: " + ", ".join(missing_read),
            code="permission_requires_read",
        )
    return wanted

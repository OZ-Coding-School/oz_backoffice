# 15. P3-3a 과정·기수 담당자 관리 API

- 상태: PR 진행 중
- 관련 PR: (작성 예정)
- 관련 계획: `docs/implement_plans/mentoring_phase1_backend.md` P3 (P3-3a)
- 이전 기록: [14. P3-2b 운영진 가입 신청 승인·반려](14_p3_2b_staff_registration_review.md)

## 배경
가입 승인(P3-2b)은 신청한 담당을 처음 한 번 만든다. 그 뒤 담당을 추가하거나 회수할 방법이 없었다. 최고 관리자가 과정·기수 담당자를 배정·해제하고, 그때 권한(`user_roles`)이 함께 맞춰지게 한다(D4). 회원 역할 직접 관리는 다음 PR(P3-3b)에서 한다.

## 구현 내용

| 경로 | 역할 |
| --- | --- |
| `access/application/roles.py`, `access/.../repositories.py` | `RoleAssignmentService.revoke`, `UserRoleRepository.remove`(역할·범위로 회수) |
| `organization/.../repositories.py` | `EmployeeRepository.list_by_ids`(목록의 직원 → 회원 일괄 조회) |
| `organization/application/staff_roles.py` | 담당 역할 → 권한 역할 매핑과 부여·회수 Protocol. 가입 승인과 담당자 배정이 함께 쓴다(리팩터링 커밋으로 분리) |
| `organization/application/staff_service.py` | `StaffAssignmentService.list_members / assign / unassign`. 배정은 담당 가능 대상, 직원 존재, 중복 배정을 검사한 뒤 담당자 행과 역할을 함께 만든다. 해제는 담당자 행과 역할을 함께 지운다. 둘 다 감사 로그 |
| `organization/presentation/staff_router.py` | `GET·POST /admin/bootcamps/{bootcamp_id}/staffs`, `DELETE .../{staff_id}`, 기수도 같은 모양. 권한 `role.assign` |
| `tests/` | 역할 회수, 직원 일괄 조회, 서비스(실제 DB: 배정→역할, 해제→회수, 과정·기수 역할 독립, 오류 4종, 다른 기수의 담당자 ID 거부), API(배정 → 해당 직원의 `/me` 역할 → 해제 후 역할 없음, 매니저 403, 409·404·422·401) |

## 주요 결정
- 담당자 1건 = 역할 1건이다. 담당자 유일 제약 (직원, 대상, 역할)과 역할 유일 제약 (회원, 역할, 범위, 대상)이 1:1로 대응한다. 그래서 해제할 때 해당 역할만 정확히 회수한다. 같은 사람의 과정 담당과 기수 담당은 범위가 달라 서로 영향이 없다.
- 담당자를 배정할 수 있는 대상은 가입 신청과 같다. 활성 과정이거나 준비·진행 중인 기수여야 한다. 해제는 대상 상태와 관계없이 할 수 있다.
- 해제 경로의 담당자 ID가 그 과정·기수 소속이 아니면 404다. 다른 기수의 담당자를 경로만 바꿔 지울 수 없다.
- 과정·기수 엔드포인트는 같은 모양이다. 처음에는 등록 함수로 묶으려 했다. 하지만 FastAPI는 데코레이터 시점에 경로 파라미터를 분석해서 이름을 나중에 바꿀 수 없었다. 그래서 엔드포인트 6개를 명시적으로 쓰고 공통 로직만 헬퍼로 묶었다.

## 검증
- 컨테이너: ruff, ruff format, mypy(src strict, tests), lint-imports, pytest **236개 통과**

## 남은 작업
- P3-3b: 회원 역할 관리 API
- P4: 직원 목록 API (담당자 배정 화면에서 직원을 고르기 위해 필요)
